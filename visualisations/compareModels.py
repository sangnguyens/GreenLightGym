import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns; sns.set()
import argparse
import numpy as np
from matplotlib.patches import Patch

### Latex font in plots
plt.rcParams['font.serif'] = "cmr10"
plt.rcParams['font.family'] = "serif"
plt.rcParams['font.size'] = 24

plt.rcParams['legend.fontsize'] = 20
plt.rcParams['legend.loc'] = 'upper right'
plt.rcParams['axes.labelsize'] = 20
plt.rcParams['axes.formatter.use_mathtext'] = True
plt.rcParams['xtick.labelsize'] = 18
plt.rcParams['ytick.labelsize'] = 18
plt.rcParams['text.usetex'] = False
plt.rcParams['mathtext.fontset'] = 'cm'
plt.rc('axes', unicode_minus=False)

def loadData(stepSize, stateNames):
    matlabStates = pd.read_csv(f"data/matlab/{stepSize}StepSizeStates.csv", sep=",", header=None)
    cythonStatesRK4 = pd.read_csv(f"data/cython/{stepSize}StepSizeStatesRK4.csv", sep=",")
    cythonStatesEuler = pd.read_csv(f"data/cython/{stepSize}StepSizeStatesEuler.csv", sep=",")
    matlabStates.columns = stateNames
    return matlabStates, cythonStatesRK4, cythonStatesEuler

def plotStates(matlabStates, cythonStatesRK4, cythonStatesEuler, states2plot, title):
    # fig, ax = plt.subplots()
    axes = matlabStates.plot(x="Time", y=states2plot, subplots=True, linewidth=3, alpha=0.5, label=["Matlab"]*len(states2plot))
    cythonStatesRK4.plot(x="Time", y=states2plot, subplots=True, ax=axes, linewidth=3, alpha=0.5, linestyle="--",  label=["RK4"]*len(states2plot))
    cythonStatesEuler.plot(x="Time", y=states2plot, subplots=True, ax=axes, linewidth=3, alpha=0.5, linestyle="-.",  label=["Euler"]*len(states2plot))

    for ax in axes[1:]:
        ax.legend().remove()
    # set set ylabels to column names
    for i, ax in enumerate(axes):
        ax.set_ylabel(states2plot[i])
    plt.suptitle(title)
    plt.show()

def plotDiffStates(matlabStates, cythonStatesRK4, cythonStatesEuler, states2plot, title):
    # fig, ax = plt.subplots()
    # axes = matlabStates.plot(x="Time", y=states2plot, subplots=True, linewidth=3, alpha=0.5, label=["Matlab"]*len(states2plot))
    
    diffRK4 = cythonStatesRK4[states2plot] - matlabStates[states2plot]
    diffEuler = cythonStatesEuler[states2plot] - matlabStates[states2plot]

    # add time to diff dataframes
    diffRK4["Time"] = cythonStatesRK4["Time"]
    diffEuler["Time"] = cythonStatesEuler["Time"]

    axes = diffRK4.plot(x="Time", y=states2plot, subplots=True, linewidth=3, alpha=0.5, linestyle="--",  label=[r"error RK4"]*len(states2plot))
    diffEuler.plot(x="Time", y=states2plot, subplots=True, ax=axes, linewidth=3, alpha=0.5, linestyle="-.",  label=[r"error Euler"]*len(states2plot))

    for ax in axes[1:]:
        ax.legend().remove()
    # set set ylabels to column names
    for i, ax in enumerate(axes):
        ax.set_ylabel(states2plot[i])
    plt.suptitle(title)
    plt.show()

def relMSEdf(matlabStates, cythonStatesRK4, cythonStatesEuler, states2plot):
    relSqErrRK4 = ((cythonStatesRK4[states2plot] - matlabStates[states2plot])**2/abs(matlabStates[states2plot]))
    relSqErrEuler = ((cythonStatesEuler[states2plot] - matlabStates[states2plot])**2/abs(matlabStates[states2plot]))

    # mean relative error per state variable
    relSqErrRK4 = relSqErrRK4.mean(axis=0)
    relSqErrEuler = relSqErrEuler.mean(axis=0)

    # join the two dataframes
    relSqErrRK4 = pd.DataFrame(relSqErrRK4, columns=["RK4"])
    relSqErrEuler = pd.DataFrame(relSqErrEuler, columns=["Euler"])
    relSqError = relSqErrEuler.join(relSqErrRK4, how="outer")
    relSqError = relSqError.reset_index()
    relSqError = relSqError.rename(columns={"index": "State"})
    # replace inf and nan with 10e10
    relSqError = relSqError.replace([np.inf], 10e10)
    relSqError = relSqError.fillna(10e10)
    return relSqError

def groupedBarPlotRelErrors(relSqErrors, stepsizes, barColors):
    # plot the dataframes in stacked bar plot
    width = 0.11  # the width of the bars
    x = np.arange(relSqErrors[0].shape[0])
    fig, ax = plt.subplots(layout='constrained')
    patterns = ["", "/"]
    colorPatches = [Patch(color=color, label=f'Step size: {category}') for color, category in zip(barColors, stepsizes)]
    patternPatches = [Patch(hatch=pattern, label=f'{category}') for pattern, category in zip(patterns, ["Euler","RK4"])]
    for i, relSqError in enumerate(relSqErrors):
        rects = ax.bar(x + width*2*i, relSqError["Euler"], width, color=barColors[i], hatch=patterns[0])
        rects = ax.bar(x + width*(2*i+1), relSqError["RK4"], width, color=barColors[i], hatch=patterns[1])

    # align labels
    ax.set_xticks(x+width*4, relSqError["State"], rotation=45, ha="right")
    ax.set_yscale("log")
    ax.legend(handles=colorPatches + patternPatches, loc='upper left')#, ncol=len(patterns)+len(barColors))
    ax.set_ylim(top=10e0)
    plt.show()

if __name__ == "__main__":
    # parse arguments for stepsize
    parser = argparse.ArgumentParser(description='Compare Matlab and Cython implementation of GreenLight.')
    parser.add_argument('--stepsize', type=str, default="60s", help='Stepsize of the simulation')
    args = parser.parse_args()

    stateNames = ["Time", "co2Air", "co2Top", "tAir", "tTop", "tCan", "tCovIn", "tCovE", "tThScr", \
                "tFlr", "tPipe", "tSo1", "tSo2", "tSo3", "tSo4", "tSo5", "vpAir", "vpTop", "tLamp", \
                "tIntLamp", "tGroPipe", "tBlScr", "tCan24", "cBuf", "cLeaf", "cStem", "cFruit", "tCanSum"]
    cropStates = stateNames[22:]

    # load in results for different step sizes
    stepsizes = ["var", "3s", "4s"]
    barColors = ["C00", "C01", "C02", "C03", "C04"]
    results = [loadData(stepsize, stateNames) for stepsize in stepsizes]
    relSqErrors = []

    for i, stepsize in enumerate(stepsizes):
        #load data
        matlabStates, cythonStatesRK4, cythonStatesEuler = results[i]
        # compute relative mean error per state variable
        relSqError = relMSEdf(matlabStates, cythonStatesRK4, cythonStatesEuler, stateNames[1:])
        relSqErrors.append(relSqError)

    groupedBarPlotRelErrors(relSqErrors, stepsizes, barColors)

    # plotDiffStates(matlabStates, cythonStatesRK4, cythonStatesEuler, ["tAir", "tTop", "tCan", "tCovIn", "tCovE", "tThScr", "tFlr", "tPipe"], "Comparison of Temperature States Part 1 Matlab vs RK4 vs Euler")

    print(relSqErrors[-1])

    # # Plot crop states
    # plotStates(matlabStates, cythonStatesRK4, cythonStatesEuler, cropStates, "Comparison of Crop States Matlab vs RK4 vs Euler")
    # # # plot temperature states
    # plotStates(matlabStates, cythonStatesRK4, cythonStatesEuler, ["tAir", "tTop", "tCan", "tCovIn", "tCovE", "tThScr", "tFlr", "tPipe"], "Comparison of Temperature States Part 1 Matlab vs RK4 vs Euler")
    # plotStates(matlabStates, cythonStatesRK4, cythonStatesEuler, ["tSo1", "tSo2", "tSo3", "tSo4", "tSo5", "tLamp", "tIntLamp", "tGroPipe", "tBlScr", "tCan24"], "Comparison of Temperature States Part 2 Matlab vs RK4 vs Euler")
    # # plot co2 states and pressure
    # plotStates(matlabStates, cythonStatesRK4, cythonStatesEuler, ["co2Air", "co2Top", "vpAir", "vpTop"], "Comparison of CO2 and Pressure States Matlab vs RK4 vs Euler")
