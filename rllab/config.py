import os.path as osp
import os

PROJECT_PATH = osp.abspath(osp.join(osp.dirname(__file__), '..'))

LOG_DIR = PROJECT_PATH + "/data"

DOCKER_IMAGE = "DOCKER_IMAGE"

KUBE_PREFIX = "rllab_"

DOCKER_LOG_DIR = "/tmp/expt"

POD_DIR = PROJECT_PATH + "/.pods"

AWS_S3_PATH = None

AWS_IMAGE_ID = None

AWS_INSTANCE_TYPE = "m4.2xlarge"

AWS_KEY_NAME = "AWS_KEY_NAME"

AWS_SPOT = True

AWS_SPOT_PRICE = '1.0'

AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY", None)

AWS_ACCESS_SECRET = os.environ.get("AWS_ACCESS_SECRET", None)

AWS_IAM_INSTANCE_PROFILE_NAME = "rllab"

AWS_SECURITY_GROUPS = ["rllab"]

AWS_REGION_NAME = "us-east-1"

CODE_SYNC_IGNORES = ["*.git/*", "*data/*"]

DOCKER_CODE_DIR = "/root/code/rllab"

AWS_CODE_SYNC_S3_PATH = "s3://to/be/overriden/in/personal"

KUBE_DEFAULT_RESOURCES = {
    "requests": {
        "cpu": 1.5,
    }
}

KUBE_DEFAULT_NODE_SELECTOR = {
    "aws/type": "m4.xlarge",
}

from config_personal import *
