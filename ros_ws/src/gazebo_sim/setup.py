from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'gazebo_sim'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('gazebo_sim/launch/*.launch.py')),
        (os.path.join('share', package_name, 'worlds'), glob('gazebo_sim/worlds/*.sdf')),
        (os.path.join('share', package_name, 'configs'), glob('gazebo_sim/configs/*')),
        (os.path.join('share', package_name, 'models', 'diff_drive'), glob('gazebo_sim/models/diff_drive/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='jjrzov@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [ 
        ],
    },
)
