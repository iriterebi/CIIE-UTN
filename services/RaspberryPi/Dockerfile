# Imagen única del controller: self-contained para deploy en la Pi (Ros2Strategy, rclpy real) y,
# vía bind-mount, entorno de iteración local con rclpy real (targets ros.* del Makefile).
# ROS 2 Jazzy = Ubuntu 24.04 = Python 3.12 (ver spec 2026-07-03-empaquetado-deploy-raspberrypi).
# Reemplaza a Dockerfile.ros: el bind-mount de dev (-v $(CURDIR):/app) sobrescribe en runtime
# el código COPYado más abajo, así que no hace falta un Dockerfile separado para dev.
FROM docker.io/library/ros:jazzy

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

# Código self-contained (artefacto portable para deploy); en dev, el bind-mount de los targets
# ros.* (-v $(CURDIR):/app) lo sobrescribe en runtime para iterar sin rebuild.
COPY controller/ ./controller/
COPY cli/ ./cli/
COPY pyproject.toml ./

# El ENTRYPOINT /ros_entrypoint.sh (heredado de ros:jazzy) sourcea /opt/ros/jazzy/setup.bash
# y ejecuta el CMD, dejando rclpy importable.
CMD ["python", "-m", "controller"]
