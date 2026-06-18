.PHONY: up_dev
up_dev:
	uv run -m controller

.DEFAULT_GOAL := up_dev

# --- ROS 2 (Jazzy) en Podman: correr Ros2Strategy con rclpy real ---
# Requiere podman instalado (ver sección "Correr Ros2Strategy con Podman" en CLAUDE.md).
# Podman es rootless: no necesita grupo ni daemon.
# Prefijo localhost/ porque podman guarda las imágenes locales en ese namespace.
IMAGE := localhost/labs-remoto/controller-ros:jazzy

.PHONY: ros.build ros.verify ros.test ros.shell ros.run
ros.build:
	podman build -f Dockerfile.ros -t $(IMAGE) .

ros.verify:
	podman run --rm $(IMAGE) \
		python -c "import rclpy; from std_msgs.msg import String; print('rclpy + std_msgs OK')"

ros.test:
	# PYTEST_DISABLE_PLUGIN_AUTOLOAD evita que los plugins pytest de ROS
	# (launch_testing, etc., visibles vía --system-site-packages) choquen con pytest 9.x.
	podman run --rm -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 -v "$(CURDIR)":/app $(IMAGE) python -m pytest

ros.shell:
	podman run --rm -it --network=host -v "$(CURDIR)":/app $(IMAGE) bash

ros.run:
	podman run --rm --network=host -v "$(CURDIR)":/app -e LOCAL_STRATEGY=Ros2Strategy $(IMAGE)
