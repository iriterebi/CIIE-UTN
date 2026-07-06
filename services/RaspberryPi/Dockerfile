# ---- Stage: base --------------------------------------------------------------
# ROS 2 Jazzy + venv + deps compartidas. SIN código de la app. Lo usan los targets
# ros.* del Makefile, siempre junto a un bind-mount de $(CURDIR) sobre /app (dev/
# iteración local con rclpy real, sin rebuild por cada cambio).
# ROS 2 Jazzy = Ubuntu 24.04 = Python 3.12 (ver spec 2026-07-03-empaquetado-deploy-raspberrypi).
FROM docker.io/library/ros:jazzy AS base

# Deps del controller (mismas que pyproject.toml) + pytest (para ros.test), en un venv con
# --system-site-packages para ver rclpy/std_msgs del Python del sistema (ROS).
# ros:jazzy no trae ensurepip → instalar python3-venv primero.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-venv \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/venv --system-site-packages \
 && /opt/venv/bin/pip install --no-cache-dir \
        "pydantic>=2.11.10" \
        "pydantic-settings>=2.13.1" \
        "python-dotenv>=1.1.1" \
        "requests>=2.32.5" \
        "pyserial>=3.5" \
        "websockets>=15.0" \
        "pytest>=8.3.0"

ENV PATH="/opt/venv/bin:${PATH}"
# Mismo dominio DDS que el agente ROS de la Pi (para descubrirse por DDS).
ENV ROS_DOMAIN_ID=42
# Forzar UDPv4 en Fast DDS: el agente ROS corre en OTRO contenedor con su propio /dev/shm,
# así que el transporte por memoria compartida (default same-host) no entrega datos entre
# contenedores aunque el descubrimiento (UDP multicast) sí cruce. UDPv4 lo resuelve.
ENV FASTDDS_BUILTIN_TRANSPORTS=UDPv4
WORKDIR /app

# El ENTRYPOINT /ros_entrypoint.sh (heredado de ros:jazzy) sourcea /opt/ros/jazzy/setup.bash
# y ejecuta el CMD, dejando rclpy importable.
# CMD acá (no repetido en `final`): `final` extiende este stage y lo hereda tal
# cual, ya que continúa la misma lineage de filesystem (no hay COPY --from=).
CMD ["python", "-m", "controller"]

# ---- Stage: final (artefacto de deploy) ----------------------------------------
# Extiende `base` linealmente (mismo filesystem, sin COPY --from=: no hay nada que
# "tirar" de base, a diferencia del patrón builder/runtime de Api/WebClient donde el
# stage final usa una imagen distinta y más liviana). Agrega el código self-contained
# + defaults de deploy horneados, para arrancar standalone (docker run/compose) sin
# bind-mount de código y con un .env mínimo (solo lo que varía por deploy).
FROM base AS final

COPY controller/ ./controller/
COPY cli/ ./cli/
COPY pyproject.toml ./

# Defaults de deploy (Ros2Strategy). env_file/-e en runtime siempre gana sobre
# el ENV horneado acá (precedencia estándar de Docker), así que siguen siendo
# overrideables si hiciera falta.
#
# SERVER_URL y ARDUINO_PORT NO se hornean a propósito: Config los exige sin
# default (varían por deploy / ARDUINO_PORT es requerido igual aunque
# Ros2Strategy no lo use — bug de config.py fuera de alcance acá). Siguen
# viniendo de .env/-e siempre.
ENV LOCAL_STRATEGY=Ros2Strategy
ENV REMOTE_STRATEGY=WsStrategy
ENV MOCK_ROBOT=0
ENV CREATE_DEFAULT_METADATA=1
ENV METADATA_FILE=/app/data/robot-metadata.json
ENV ROS2_NODE_NAME=labs_remoto_robot
ENV ROS2_COMMAND_TOPIC=/inorbit/custom_command
# Mismo valor que ROS_DOMAIN_ID (stage base) pero es OTRA variable: esta es el
# campo de Config (app), aquella es el ENV de infra DDS del SO. No deduplicar.
ENV ROS2_DATA_TOPIC=/inorbit/custom_data
ENV ROS2_DOMAIN_ID=42
