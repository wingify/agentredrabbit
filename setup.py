try:
    from setuptools import setup, find_packages
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

from agentredrabbit import __version__


setup(
    name="agentredrabbit",
    version=__version__,
    author="Rohit Yadav",
    author_email="rohit.yadav@wingify.com",
    url="https://github.com/wingify/agentredrabbit",
    description="Redis to RabbitMQ transport agent",
    long_description="Transport agent that moves data from Redis to RabbitMQ",
    platforms=("Any",),
    packages=find_packages(exclude=["tests"]),
    package_data={"": ["LICENSE",],},
    install_requires=[
        "hiredis",
        "pika",
        "redis",
    ],
    tests_require=[
        "nose",
        "mock",
    ],
    test_suite="nose.collector",
    include_package_data = True,
    zip_safe = False,
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
    ],
    entry_points="""
    [console_scripts]
    agentredrabbit = agentredrabbit.agentredrabbit:main
    """,
)
