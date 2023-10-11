import gymnasium as gym
from gymnasium.spaces import Box

import numpy as np
import pandas as pd
from typing import Optional, Tuple, Any, List, Dict
from RLGreenLight.environments.GreenLightCy import GreenLight as GL
from RLGreenLight.environments.pyutils import loadWeatherData

from datetime import date

class GreenLightBase(gym.Env):
    """
    Python wrapper class for the GreenLight model implemented in Cython.
    As input we get the weather data, number of variables for states, inputs and disturbances, and whether and which lamps we use.
    Argument definitions are in the init function.
    """
    def __init__(self, weatherDataDir:str, # path to weather data
                 location: str,             # location of the recorded weather data
                 dataSource: str,           # source of the weather data
                 h: float,                  # [s] time step for the RK4 solver
                 nx: int,                   # number of states 
                 nu: int,                   # number of control inputs
                 nd: int,                   # number of disturbances
                 noLamps: int,              # whether lamps are used
                 ledLamps: int,             # whether led lamps are used
                 hpsLamps: int,             # whether hps lamps are used
                 intLamps: int,             # whether interlighting lamps are used
                 dmfm: float,               # [kg [FM] m^-2] dry matter fruit mass
                 seasonLength: int,         # [days] length of the growing season
                 predHorizon: int,          # [days] number of future weather predictions
                 timeinterval: int,         # [s] time interval in between observations
                 controlSignals: List[str],  # list with all the control signals we aim to with RL/controller
                 modelObsVars: int,          # number of variables we observe from the model
                 weatherObsVars: int,        # number of variables we observe from the weather data
                 obsLow: List[float],       # lower bound for the observation space
                 obsHigh: List[float],      # upper bound for the observation space
                 rewardCoefficients: List[float], # coefficients for the reward function
                 penaltyCoefficients: List[float], # coefficients for the penalty function
                 options: Optional[Dict[str, Any]] = None, # options for the environment (e.g. specify starting date)
                 training: bool = True,     # whether we are training or testing
                 ) -> None:

        super(GreenLightBase, self).__init__()
        # number of seconds in the day
        c = 86400

        # arguments that are kept the same over various simulations
        self.weatherDataDir = weatherDataDir
        self.location = location
        self.dataSource = dataSource
        self.h = h
        self.nx = nx
        self.nu = nu
        self.nd = nd
        self.noLamps = noLamps
        self.ledLamps = ledLamps
        self.hpsLamps = hpsLamps
        self.intLamps = intLamps
        self.dmfm = dmfm
        self.seasonLength = seasonLength
        self.predHorizon = predHorizon
        self.timeinterval = timeinterval
        self.controlSignals = controlSignals
        self.N = int(seasonLength*c/timeinterval)           # number of timesteps to take for python wrapper
        self.solverSteps = int(self.timeinterval/self.h)    # number of steps the solver takes between timeinterval
        self.Np = int(predHorizon*c/timeinterval)           # the prediction horizon in timesteps for our weather predictions
        self.modelObsVars = modelObsVars
        self.weatherObsVars = weatherObsVars
        self.rewardCoefficients = rewardCoefficients
        self.penaltyCoefficients = penaltyCoefficients
        self.options = options
        self.training = training

        # set up the action and observation space
        self.action_space = Box(low=-1, high=1, shape=(len(controlSignals),), dtype=np.float32)
        self.observation_space = Box(low=-1e4, high=1e4, shape=(self.modelObsVars+(self.Np+1)*self.weatherObsVars,), dtype=np.float32)

        # specify which signals we want to control
        controlIndices = {"uBoil": 0, "uCO2": 1, "uThScr": 2, "uVent": 3, "uLamp": 4, "uIntLamp": 5, "uGroPipe": 6, "uBlScr": 7}
        self.controlIdx = np.array([controlIndices[controlInput] for controlInput in controlSignals], dtype=np.int8)

        # lower and upper bounds for air temperature, co2 concentration, humidity
        self.obsLow = np.array(obsLow)
        self.obsHigh = np.array(obsHigh)


    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        Given an action computed by some agent, we simulate the next state of the system.
        The system is modelled by the GreenLight model implemented in Cython.
        We have to control the boiler valve, co2, thermal screen, roof vent, lamps, internal lamps, grow pipes and blackout screen.
        """
        # scale the action to the range of the control inputs, which is between [0, 1]
        action = (action-self.action_space.low)/(self.action_space.high-self.action_space.low)
        self.GLModel.step(action, self.controlIdx)

        # state = self.GLModel.getStatesArray()
        obs = self._getObs()
        if self._terminalState(obs):
            self.terminated = True
            reward = 0
        else:
            reward = self._reward(obs, action)

        self.prevYield = obs[3]

        # additional information to return
        info = {"controls": self.GLModel.getControlsArray(),
                "Time": self.GLModel.time}

        return (obs,
            reward, 
            self.terminated, 
            False,
            info
            )

    def _reward(self, obs: np.ndarray, action: np.ndarray) -> float:
        raise NotImplementedError

    def _computePenalty(self, obs: np.ndarray) -> float:
        """    
        Function that computes the penalty for constraint violations.

        Penalty is the sum of the squared differences between the observation and the bounds.
        No penalty is given if the system variables are within the bounds.

        Args:
            obs (np.ndarray): observation of the system variables
        Returns:
            penalty (np.ndarray): penalty for constraint violations
        """        
        Npen = self.obsLow.shape[0]
        lowerbound = self.obsLow[:] - obs[:Npen]
        lowerbound[lowerbound < 0] = 0
        upperbound = obs[:Npen] - self.obsHigh[:]
        upperbound[upperbound < 0] = 0
        return lowerbound**2 + upperbound**2

    def _getObs(self) -> np.ndarray:
        """
        Function that extracts the observations from the underlying GreenLight model.

        Returns:
            obs (np.ndarray): observation of the system variables
        """
        modelObs = self.GLModel._getObs()
        weatherIdx = [self.GLModel.timestep*self.solverSteps] + [(ts + self.GLModel.timestep)*self.solverSteps for ts in range(1, self.Np)]
        weatherObs = self.weatherData[weatherIdx, :self.weatherObsVars].flatten()
        return np.concatenate([modelObs, weatherObs], axis=0)

    def _terminalState(self, obs: np.ndarray) -> bool:
        """
        Function that checks whether the simulation has reached a terminal state.
        Terminal obs are reached when the simulation has reached the end of the growing season.
        Or when there are nan or inf in the state values.
        """
        if self.GLModel.timestep >= self.N:
            return True
        # check for nan and inf in state values
        elif np.isnan(obs).any() or np.isinf(obs).any():
            print("Nan or inf in states")
            return True
        return False

    def _getTime(self) -> float:
        """
        Get time in days since 01-01-0001 upto the starting day of the simulation.
        """
        return self.GLModel.time

    def _getTimeInDays(self) -> float:
        """
        Get time in days since 01-01-0001 upto the starting day of the simulation.
        """
        d0 = date(1, 1, 1)
        d1 = date(self.growthYear, 1, 1)
        delta = d1 - d0
        return delta.days + self.startDay

    def scale(self, r, rmin, rmax):
        """
        Function that scales input between [0, 1].
        Either for the reward or penalty.
        Can take in a single value or an array.
        """
        return (r-rmin)/(rmax-rmin)

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Container function that resets the environment.
        """
        raise NotImplementedError


class GreenLightCO2(GreenLightBase):
    """
    Child class of GreenLightBase.
    Starts with a fully mature crop that is ready for harvest.
    The start dates are early year, (January and Februari), which reflects the start of the harvest season.
    """
    def __init__(self,
                 cLeaf: float = 2.5e5,
                 cStem: float = 0.9e5,
                 cFruit: float = 2.8e5,
                 tCanSum: float  = 1035,
                 tomatoPrice: float = 1.2,
                 co2Price: float = 0.19,
                 **kwargs,
                 ) -> None:
        super(GreenLightCO2, self).__init__(**kwargs)
        self.cLeaf = cLeaf
        self.cStem = cStem
        self.cFruit = cFruit
        self.tCanSum = tCanSum
        self.tomatoPrice = tomatoPrice
        self.co2Price = co2Price

    def _reward(self, obs: np.ndarray, action: np.ndarray) -> float:
        """
        Function that computes the reward for a given observation.
        Reward consists of the harvest over the past time step minus the costs of the control inputs.
        """
        harvest = obs[4] / self.dmfm                                            # [kg [FM] m^-2]
        co2resource = self.GLModel.co2InjectionRate * self.timeinterval * 1e-6  # [kg m^-2 900s^-1]
        reward = harvest*self.tomatoPrice - co2resource*self.co2Price           # [euro m^-2]
        abs_penalty = self._computePenalty(obs)
        return self.scale(reward, self.rmin, self.rmax) - self.scale(abs_penalty, self.penmin, self.penmax)

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset the environment to a random initial state.
        Randomness is introduced by the growth year and start day.
        Which affect the weather data observed.
        """
        super().reset(seed=seed)
        if self.training:
            self.growthYear = np.random.choice([year for year in range(2012, 2020)])
            self.startDay = np.random.choice([day for day in range(0, 200)])
        else:
            self.growthYear = self.options["growthYear"]
            self.startDay = self.options["startDay"]

        # load in weather data for this simulation
        self.weatherData = loadWeatherData(self.weatherDataDir, self.location, self.dataSource, self.growthYear, self.startDay, self.seasonLength, self.predHorizon, self.h, self.nd)
        # self.actions = np.zeros((self.nu,))

        # compute days since 01-01-0001
        # as time indicator by the model
        timeInDays = self._getTimeInDays()

        # initialize the model in C, set the crop state to mature crop
        self.GLModel = GL(self.weatherData, self.h, self.nx, self.nu, self.nd, self.noLamps, self.ledLamps, self.hpsLamps, self.intLamps, self.solverSteps, timeInDays)
        self.GLModel.setCropState(self.cLeaf, self.cStem, self.cFruit, self.tCanSum)

        # max reward for fruit growth
        self.rmax = 1e-6*self.GLModel.maxHarvest/self.dmfm * self.timeinterval * self.tomatoPrice   # [€ kg^-1 [FM] m^-2]
        self.rmin = - 1e-6 * self.GLModel.maxco2rate * self.co2Price                                # [€ kg^-1 m^2]'

        self.penmax = 9e6                                                                           # max penalty on CO2 bound
        self.penmin = 0                                                                             # min penalty on CO2 bound

        self.terminated = False

        return self._getObs(), {}

class GreenLightHarvest(GreenLightBase):
    """
    Child class of GreenLightBase. This class also models the greenhouse crop production process.
    But starts with a fully mature crop that is ready for harvest.
    The start dates are early year, (January and Februari), which reflects the start of the harvest season.
    """
    def __init__(self,
                 cLeaf: float = 2.5e5,
                 cStem: float = 0.9e5,
                 cFruit: float = 2.8e5,
                 tCanSum: float  = 1035,
                 tomatoPrice: float = 1.2,
                 co2Price: float = 0.19,
                 gasPrice: float = 0.35,
                 electricityPrice: float = 0.1,
                 energyContentGas: float  = 31.65,
                 **kwargs,
                 ) -> None:
        super(GreenLightHarvest, self).__init__(**kwargs)
        self.cLeaf = cLeaf
        self.cStem = cStem
        self.cFruit = cFruit
        self.tCanSum = tCanSum
        self.tomatoPrice = tomatoPrice
        self.co2Price = co2Price
        self.gasPrice = gasPrice
        self.electricityPrice = electricityPrice
        self.energyContentGas = energyContentGas

    def _getObs(self) -> np.ndarray:
        modelObs = self.GLModel.getHarvestObs()
        weatherIdx = [self.GLModel.timestep*self.solverSteps] + [(ts + self.GLModel.timestep)*self.solverSteps for ts in range(1, self.Np)]
        weatherObs = self.weatherData[weatherIdx, :self.weatherObsVars].flatten()
        return np.concatenate([modelObs, weatherObs], axis=0)

    def _reward(self, obs: np.ndarray, action: np.ndarray) -> float:
        """
        Compute the reward given the harvest of the model.
        """
        harvest = obs[4] / self.dmfm                                                # [kg [FM] m^-2]
        co2resource = obs[8] * self.timeinterval * 1e-6                             # [kg m^-2 900s^-1]
        electricityResource = obs[9] * (self.timeinterval/3600) * 1e-3              # [kWh m^-2]
        heatResource = (obs[10] * self.timeinterval* 1e-6)/self.energyContentGas    # [MJ m^-2 900s^-1]
        
        reward = harvest*self.tomatoPrice - co2resource*self.co2Price -\
         electricityResource*self.electricityPrice - heatResource*self.gasPrice     # [euro m^-2]
        penalty = np.dot(self._computePenalty(obs), self.penaltyCoefficients)        # penalty for constraint violations
        return reward - penalty

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset the environment to a random initial state.
        Randomness is introduced by the growth year and start day.
        Which affect the weather data observed.
        """
        super().reset(seed=seed)
        if self.training:
            self.growthYear = np.random.choice([year for year in range(2012, 2020)])
            self.startDay = np.random.choice([day for day in range(0, 200)])
        else:
            self.growthYear = self.options["growthYear"]
            self.startDay = self.options["startDay"]

        # load in weather data for this simulation
        self.weatherData = loadWeatherData(self.weatherDataDir, self.location, self.dataSource, self.growthYear, self.startDay, self.seasonLength, self.predHorizon, self.h, self.nd)
        # self.actions = np.zeros((self.nu,))

        # compute days since 01-01-0001
        # as time indicator by the model
        timeInDays = self._getTimeInDays()
        
        # initialize the model in C, set the crop state to mature crop
        self.GLModel = GL(self.weatherData, self.h, self.nx, self.nu, self.nd, self.noLamps, self.ledLamps, self.hpsLamps, self.intLamps, self.solverSteps, timeInDays)
        self.GLModel.setCropState(self.cLeaf, self.cStem, self.cFruit, self.tCanSum)

        self.terminated = False
        
        return self._getObs(), {}



if __name__ == "__main__":
    pass
