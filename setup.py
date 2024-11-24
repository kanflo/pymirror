from setuptools import setup

setup(name="PyMirror",
      version="0.1",
      description="One more Magic Mirror, this time in Python",
      url="http://github.com/kanflo/pymirror",
      author="Johan Kanflo",
      author_email="johan.kanflo@bitfuse.net",
      license="MIT",
      packages=["pymirror"],
      install_requires=["requests", "coloredlogs", "python-dateutil", "pytz", "pygame", "mqttwrapper"],
      zip_safe=False
)
