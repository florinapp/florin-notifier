import os
import yaml


config_file = os.getenv('CONFIG_FILE')
assert config_file is not None

with open(config_file) as f:
    config = yaml.load(f)
