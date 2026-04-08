"""Dynamically generate docker-compose files for each Task.

Each Task gets its own compose file with isolated container names, network,
ports, and volume mounts for trajectory collection.
"""
# ASE/orchestrator/compose_gen.py
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


def generate_compose(
    task_id: str,
    ports: Dict[str, int],
    task_dir: Path,
    user_mode: str = "interactive",
    llm_config: Optional[Dict[str, str]] = None,
    agent_image: str = "ase-agent",
    replay_config: Optional[Dict[str, Any]] = None,
) -> Path:
    """Generate a docker-compose.yml for a specific Task.

    Args:
        task_id: Unique task identifier (e.g. "task-001")
        ports: Port mapping from PortAllocator
        task_dir: Directory for this task's data (trajectories, etc.)
        user_mode: "interactive" or "simulated"
        llm_config: LLM API configuration override
        agent_image: Docker image name for the agent
        replay_config: If set, enables replay mode with keys:
            trajectory_path: host path to trajectory JSONL
            steps: number of steps to replay (optional)

    Returns:
        Path to generated compose file
    """
    project = f"ase-{task_id}"
    network = f"{project}-net"

    llm = llm_config or {}
    api_base = llm.get("api_base", "https://api2.aigcbest.top/v1")

    api_key = llm.get("api_key", "sk-NzLZFOtu8BlGDCGJtJMy7TpbNgCbk5vTGF9oz3Mml3IL2m0x")
    model = llm.get("model", "DeepSeek-V3")
    temperature = llm.get("temperature", "0.7")
    max_tokens = llm.get("max_tokens", "8192")

    # Ensure task directories exist
    traj_agent = task_dir / "trajectories" / "agent"
    traj_user = task_dir / "trajectories" / "user"
    traj_agent.mkdir(parents=True, exist_ok=True)
    traj_user.mkdir(parents=True, exist_ok=True)
    (task_dir / "logs").mkdir(parents=True, exist_ok=True)

    # ASE project root (for Dockerfile context and service configs)
    ase_root = Path(__file__).resolve().parent.parent

    services = {}

    # --- MongoDB ---
    services["mongodb"] = {
        "image": "docker.1ms.run/library/mongo:5.0",
        "container_name": f"{project}-mongodb",
        "restart": "unless-stopped",
        "command": "mongod --replSet rs0 --oplogSize 128",
        "volumes": [f"{project}_mongodb_data:/data/db"],
        "networks": [network],
    }

    # --- MongoDB init ---
    services["mongodb-init"] = {
        "image": "docker.1ms.run/library/mongo:5.0",
        "container_name": f"{project}-mongodb-init",
        "restart": "on-failure",
        "depends_on": ["mongodb"],
        "networks": [network],
        "command": (
            'bash -c "'
            "sleep 15; "
            "mongosh mongodb://mongodb:27017 --eval \\\""
            "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]})"
            '\\\""'
        ),
    }

    # --- Rocket.Chat ---
    services["rocketchat"] = {
        "image": "docker.1ms.run/rocketchat/rocket.chat:5.3.0",
        "container_name": f"{project}-rocketchat",
        "restart": "unless-stopped",
        "depends_on": ["mongodb"],
        "environment": {
            "MONGO_URL": "mongodb://mongodb:27017/rocketchat?replicaSet=rs0",
            "ROOT_URL": f"http://localhost:{ports['rocketchat']}",
            "PORT": "3000",
            "ADMIN_USERNAME": "aseadmin",
            "ADMIN_PASS": "admin_pass_2026",
            "ADMIN_EMAIL": "admin@ase.local",
            "ADMIN_NAME": "ASE Admin",
            "Show_Setup_Wizard": "completed",
            "OVERWRITE_SETTING_Show_Setup_Wizard": "completed",
        },
        "ports": [f"{ports['rocketchat']}:3000"],
        "networks": [network],
    }

    # --- Email Server ---
    services["mailserver"] = {
        "image": "docker.1ms.run/mailserver/docker-mailserver:13.3.1",
        "container_name": f"{project}-mailserver",
        "hostname": "mail.ase.local",
        "restart": "unless-stopped",
        "ports": [
            f"{ports['smtp']}:25",
            f"{ports['smtp_submit']}:587",
            f"{ports['imap']}:143",
            f"{ports['imaps']}:993",
        ],
        "volumes": [
            f"{project}_maildata:/var/mail",
            f"{project}_mailstate:/var/mail-state",
            f"{project}_maillogs:/var/log/mail",
            f"{str(ase_root / 'services' / 'email' / 'config')}:/tmp/docker-mailserver/",
        ],
        "environment": [
            "ENABLE_SPAMASSASSIN=0",
            "ENABLE_CLAMAV=0",
            "ENABLE_FAIL2BAN=0",
            "ENABLE_POSTGREY=0",
            "ENABLE_AMAVIS=0",
            "ONE_DIR=1",
            "DMS_DEBUG=0",
        ],
        "cap_add": ["NET_ADMIN"],
        "networks": [network],
    }

    # --- Web Environment ---
    services["webenv"] = {
        "image": "docker.1ms.run/library/nginx:alpine",
        "container_name": f"{project}-webenv",
        "restart": "unless-stopped",
        "ports": [f"{ports['web']}:80"],
        "volumes": [
            f"{str(ase_root / 'services' / 'web' / 'html')}:/usr/share/nginx/html:ro",
        ],
        "networks": [network],
    }

    # --- Agent Sandbox ---
    agent_env = [
        f"LLM_API_BASE={api_base}",
        f"LLM_API_KEY={api_key}",
        f"LLM_MODEL={model}",
        f"LLM_TEMPERATURE={temperature}",
        f"LLM_MAX_TOKENS={max_tokens}",
        "AGENT_WORKSPACE=/app/workspace",
        "RC_URL=http://rocketchat:3000",
        "RC_USERNAME=agent",
        "RC_PASSWORD=agent_pass_2026",
        "IMAP_HOST=mailserver",
        "SMTP_HOST=mailserver",
        "EMAIL_USER=agent@ase.local",
        "EMAIL_PASS=agent_pass_2026",
        "ASE_ALLOW_INTERNAL_NETWORK=1",
    ]
    agent_volumes = [f"{str(traj_agent)}:/app/trajectories"]

    if replay_config:
        agent_env.append("REPLAY_MODE=1")
        agent_env.append(f"REPLAY_TRAJECTORY=/app/replay/source.jsonl")
        if replay_config.get("steps"):
            agent_env.append(f"REPLAY_STEPS={replay_config['steps']}")
        # Mount source trajectory into /app/replay/
        host_traj = replay_config["trajectory_path"]
        replay_dir = task_dir / "replay"
        replay_dir.mkdir(parents=True, exist_ok=True)
        agent_volumes.append(f"{str(replay_dir)}:/app/replay:ro")

    services["agent"] = {
        "image": agent_image,
        "container_name": f"{project}-agent",
        "restart": "unless-stopped",
        "depends_on": ["rocketchat", "mailserver"],
        "environment": agent_env,
        "volumes": agent_volumes,
        "extra_hosts": ["host.docker.internal:host-gateway"],
        "networks": [network],
    }

    # --- User Sandbox (simulated mode only) ---
    if user_mode == "simulated":
        services["user"] = {
            "image": agent_image,  # Reuse same image, different entry point
            "container_name": f"{project}-user",
            "restart": "unless-stopped",
            "depends_on": ["rocketchat", "mailserver"],
            "command": ["python", "scripts/run_simulated_user.py"],
            "environment": [
                f"LLM_API_BASE={api_base}",
                f"LLM_API_KEY={api_key}",
                f"LLM_MODEL={model}",
                f"RC_URL=http://rocketchat:3000",
                "RC_USERNAME=testuser",
                "RC_PASSWORD=test_pass_2026",
                "SMTP_HOST=mailserver",
                "IMAP_HOST=mailserver",
                "EMAIL_USER=test@ase.local",
                "EMAIL_PASS=test_pass_2026",
                f"TASK_ID={task_id}",
            ],
            "volumes": [
                f"{str(traj_user)}:/app/trajectories",
            ],
            "networks": [network],
        }

    # --- Compose document ---
    compose = {
        "services": services,
        "volumes": {
            f"{project}_mongodb_data": None,
            f"{project}_maildata": None,
            f"{project}_mailstate": None,
            f"{project}_maillogs": None,
        },
        "networks": {
            network: {"driver": "bridge"},
        },
    }

    compose_file = task_dir / "docker-compose.yml"
    with open(compose_file, "w") as f:
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Generated compose file: {compose_file}")
    return compose_file
