from setuptools import find_packages, setup

package_name = 'mock_robot'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='CIIE Team',
    maintainer_email='ciie@example.com',
    description='Nodo mock que simula robots para modo demo',
    license='MIT',
    entry_points={
        'console_scripts': [
            'mock_robot_node = mock_robot.mock_robot_node:main',
        ],
    },
)
