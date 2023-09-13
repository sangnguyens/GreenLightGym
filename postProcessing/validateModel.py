from RLGreenLight.environments.GreenLight import GreenLight
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize, VecMonitor
import yaml
import numpy as np
import pandas as pd
from RLGreenLight.environments.pyutils import days2date
import os
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("runname", type=str)
    args = parser.parse_args()

    # hyperparameters
    with open("hyperparameters/ppo/balance-rew-no-constraints.yml", "r") as f:
        params = yaml.load(f, Loader=yaml.FullLoader)
        envParams = params["GreenLight"]
        options = params["options"]
    SEED = 666
    envParams['training'] = False

    # env = GreenLight(**envParams, options=options)
    env = DummyVecEnv([lambda: GreenLight(**envParams, options=options)])
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_reward=1000, clip_obs=100)
    env = VecMonitor(env, filename=None)
    # args.runname = "cool-"
    model = PPO.load(f"trainData/models/{args.runname}/best_model.zip", env=env)
    env = model.get_env()
    obs, info = env.env_method("reset", options=options)[0]
    obs = obs.reshape(1, -1)

    N = env.get_attr("N")[0]                        # get number of time steps
    states = np.zeros((N+1, envParams["modelObsVars"]))       # array to save states
    controlSignals = np.zeros((N+1, envParams["nu"])) # array to save rule-based controls controls
    timevec = np.zeros((N+1,))                      # array to save time
    dones = [False]

    states[0, :] = obs[0, :envParams["modelObsVars"]]             # get initial states
    timevec[0] = env.env_method("getTimeInDays")[0]

    print(timevec[0])
    # print(obs)

    i=0
    while not dones[0]:
        action, _states = model.predict(obs, deterministic=True)
        obs, rewards, dones, info = env.step(action)
        states[i+1, :] = env.unnormalize_obs(obs)[0, :envParams["modelObsVars"]]
        timevec[i+1] = info[0]['Time']
        controlSignals[i+1, :] = info[0]['controls']
        rewards = env.unnormalize_reward(rewards)[0]
        # print(obs.shape)
        # print(info)
        i+=1

    states = np.insert(states, 0, timevec, axis=1)
    states = pd.DataFrame(data=states[:], columns=["Time", "Air Temperature", "CO2 concentration", "Humidity", "Fruit weight", "Fruit harvest", "PAR"])
    controlSignals = pd.DataFrame(data=controlSignals, columns=["uBoil", "uCO2", "uThScr", "uVent", "uLamp", "uIntLamp", "uGroPipe", "uBlScr"])

    states["Time"] = np.asarray(days2date(states["Time"].values, "01-01-0001"), "datetime64[s]")
    dates = states["Time"].dt.strftime("%Y%m%d")

    # check if directory exists
    if not os.path.exists(f"data/ppo/{args.runname}"):
        os.makedirs(f"data/ppo/{args.runname}")


    states.to_csv(f"data/ppo/{args.runname}/states{dates[0]}-{envParams['seasonLength']:03}.csv", index=False)
    controlSignals.to_csv(f"data/ppo/{args.runname}/controls{dates[0]}-{envParams['seasonLength']:03}.csv", index=False)

    print(states)
    print(controlSignals)
