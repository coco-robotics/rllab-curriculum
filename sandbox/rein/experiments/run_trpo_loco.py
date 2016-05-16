import os
from rllab.baselines.linear_feature_baseline import LinearFeatureBaseline
from sandbox.rein.envs.walker2d_env_x import Walker2DEnvX
from sandbox.rein.envs.swimmer_env_x import SwimmerEnvX
from sandbox.rein.envs.half_cheetah_env_x import HalfCheetahEnvX
os.environ["THEANO_FLAGS"] = "device=cpu"

from rllab.policies.gaussian_mlp_policy import GaussianMLPPolicy
from rllab.envs.normalized_env import NormalizedEnv

from rllab.algos.trpo import TRPO
from rllab.misc.instrument import stub, run_experiment_lite
import itertools

stub(globals())

# Param ranges
seeds = range(10)
# mdp_classes = [SimpleHumanoidEnv]
# mdps = [NormalizedEnv(env=mdp_class())
#         for mdp_class in mdp_classes]
mdps = [HalfCheetahEnvX()]
param_cart_product = itertools.product(
    mdps, seeds
)

for mdp, seed in param_cart_product:

    policy = GaussianMLPPolicy(
        env_spec=mdp.spec,
        hidden_sizes=(64, 32),
    )

#     baseline = GaussianMLPBaseline(
#         mdp.spec,
#         regressor_args=dict(hidden_sizes=(64, 32)),
#     )
    baseline = LinearFeatureBaseline(
        mdp.spec,
    )

    batch_size = 5000
    algo = TRPO(
        env=mdp,
        policy=policy,
        baseline=baseline,
        batch_size=batch_size,
        whole_paths=True,
        max_path_length=500,
        n_itr=5000,
        step_size=0.01,
        subsample_factor=1.0,
    )

    run_experiment_lite(
        algo.train(),
        exp_prefix="x-trpo-loco-i1",
        n_parallel=8,
        snapshot_mode="last",
        seed=seed,
        mode="lab_kube",
        dry=False,
    )
