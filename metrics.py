"""
MSc Thesis Quantitative Finance
Title: Interest rate risk due to EONIA-ESTER transition
Author: Lars ter Braak (larsterbraak@gmail.com)

Last updated: May 25th 2020
Code Author: Lars ter Braak (larsterbraak@gmail.com)

-----------------------------

Create simulation for the EONIA short rate and backtest the VaR
using the Basel Committee's Traffic Light coverage test   
(1) Perform coverage test Basel
 -
(2) Perform realness classification of ESTER + 8.5 bps wrt EONIA

Inputs
(1) EONIA, calibrated TimeGAN models
-
- 

Outputs
- Classification for the Value-at-Risk model
"""

import os

# Change to the needed working directory
os.chdir('C://Users/s157148/Documents/Github/TimeGAN')

import numpy as np
from TSTR import value_at_risk
from data_loading import create_dataset
from scipy.stats import binom
from training import RandomGenerator
import matplotlib.pyplot as plt
import pandas as pd

def load_models(epoch):        
    from models.Discriminator import Discriminator
    from models.Recovery import Recovery
    from models.Generator import Generator
    from models.Embedder import Embedder
    from models.Supervisor import Supervisor
     
    if epoch % 50 != 0:
        return 'Only insert epochs that are divisible by 50.'
    else:
        # Only use when you want to load the models
        e_model_pre_trained = Embedder('logs/e_model_pre_train', [], dimensionality = 1)
        e_model_pre_trained.load_weights('C://Users/s157148/Documents/Github/TimeGAN/weights/embedder/epoch_' + str(epoch)).expect_partial()
        e_model_pre_trained.build([])
        
        r_model_pre_trained = Recovery('logs/r_model_pre_train', [], dimensionality = 1)
        r_model_pre_trained.load_weights('C://Users/s157148/Documents/Github/TimeGAN/weights/recovery/epoch_' + str(epoch)).expect_partial()
        r_model_pre_trained.build([])
        
        s_model_pre_trained = Supervisor('logs/s_model_pre_train', [])
        s_model_pre_trained.load_weights('C://Users/s157148/Documents/Github/TimeGAN/weights/supervisor/epoch_' + str(epoch)).expect_partial()
        s_model_pre_trained.build([])
        
        g_model_pre_trained = Generator('logs/g_model_pre_train', [])
        g_model_pre_trained.load_weights('C://Users/s157148/Documents/Github/TimeGAN/weights/generator/epoch_' + str(epoch)).expect_partial()
        g_model_pre_trained.build([])
        
        d_model_pre_trained = Discriminator('logs/d_model_pre_train', []) 
        d_model_pre_trained.load_weights('C://Users/s157148/Documents/Github/TimeGAN/weights/discriminator/epoch_' + str(epoch)).expect_partial()
        d_model_pre_trained.build([])
        
        return e_model_pre_trained, r_model_pre_trained, s_model_pre_trained, g_model_pre_trained, d_model_pre_trained

def create_plot_simu(simulation_cum, T, ax):
    ax.plot(range(T), np.transpose(simulation_cum))
    ax.set_xlabel('Days')
    ax.set_ylabel('Short rate')

def create_plot_nn(equivalent, simulation, T, ax):
    ax.plot(range(T), equivalent, label = 'EONIA data')
    ax.plot(range(T), simulation, label = 'Generated data')
    ax.set_xlabel('Days')
    ax.set_ylabel('Short rate')

def image_grid(N, T, hidden_dim, recovery_model, generator_model):
    # Get the EONIA T-day real values
    EONIA = create_dataset(name='EONIA', seq_length = 20, training=False)
    EONIA = np.reshape(EONIA, (EONIA.shape[0], EONIA.shape[1])) # These T-day intervals are shuffled
        
    figure = plt.figure(figsize=(15,15))
    plt.title('Nearest neighbour in the EONIA data')
    for i in range(20):
        number = np.random.randint(N) # Simulate a random numbers
        
        # N simulations for TimeGAN calibrated on EONIA
        Z_mb = RandomGenerator(N, [T, hidden_dim])
        X_hat_scaled = recovery_model(generator_model(Z_mb)).numpy()
        simulation = np.reshape(X_hat_scaled, (N, T))
        simulation_cum = np.cumsum(simulation, axis=1)
        
        # Find the nearest neighbour in the dataset
        closest = np.mean(((EONIA - simulation[number, :])**2), axis = 1).argsort()[0]
        equivalent = EONIA[closest, :]
        
        # Start next subplot.
        if i < 10:
            ax = plt.subplot(4, 5, i + 1, title=str('Simulation ' + str(i+1)))
            create_plot_simu(simulation_cum, T, ax)
        else:
            ax = plt.subplot(4, 5, i + 1, title=str('Nearest Neighbour '+ str(i-9) ) )
            create_plot_nn(equivalent, simulation[number,:], T, ax)
        plt.grid(False)
    
    plt.tight_layout()
    return figure
 
def coverage_test_basel(generator_model, recovery_model,
                        lower=True, hidden_dim = 4):
    
    # Get the EONIA T-day real values
    EONIA = create_dataset(name='EONIA', seq_length = 20, training=False)
    EONIA = np.reshape(EONIA, (EONIA.shape[0], EONIA.shape[1])) # These T-day intervals are shuffled
        
    # Specify Nr. simulations and T
    N = 100
    T = 20
    exceedances = 0 # Initialize the number of exceedances
    
    for i in range(250): # 250 trading days
        # N simulations for TimeGAN calibrated on EONIA
        Z_mb = RandomGenerator(N, [T, hidden_dim])
        X_hat_scaled = recovery_model(generator_model(Z_mb)).numpy()
        value = np.cumsum(EONIA[i, :])[-1] # Value for T-days
        
        # Train on Synthetic, Test on Real
        if lower:
            VaR_l = value_at_risk(X_hat=X_hat_scaled, percentile=99, upper=False)
            exceedances = exceedances + int(value < VaR_l)
        else:    
            VaR_u = value_at_risk(X_hat=X_hat_scaled, percentile=99, upper=True)
            exceedances = exceedances + int(VaR_u < value)
        
    prob = binom.cdf(np.sum(exceedances), 250, .01)
    
    if prob <= binom.cdf(4, 250, 0.01):
        return 'Green', exceedances
    elif binom.cdf(4, 250, 0.01) <= prob <= binom.cdf(9, 250, 0.01):
        return 'Yellow', exceedances
    else:
        return 'Red', exceedances 
    
def ester_classifier(load_epochs=50):
    # Load the ESTER model with an additional 8.5 bps and the shuffled ids 
    idx, pre_ESTER = create_dataset(name='pre-ESTER', normalization='min-max',
                                seq_length=20, training=False, 
                                multidimensional=False, ester_probs=True,
                                include_spread = True)
   
    # Probably not necessary and does not work
    #ESTER = np.reshape(ESTER, (ESTER.shape[0], ESTER.shape[1])) # These T-day intervals are shuffled
    
    # Load the pre-trained models
    e_model, _, _, _, d_model = load_models(load_epochs)
    
    # Calculate the probabilities
    probs = d_model.predict(e_model(pre_ESTER).numpy()).numpy()
    
    results = np.zeros((pre_ESTER.shape[0],
                        pre_ESTER.shape[0] + pre_ESTER.shape[1] - 1))
    
    # Set the probabilities back at it again
    for i in range(len(idx)):
        results[idx[i], idx[i]:(idx[i] + pre_ESTER.shape[1])] = np.ravel(probs[i, :, :])
    
    probs_per_time = np.sum(results, axis = 0) / (np.count_nonzero(results, axis = 0) + 1e-11)
    
    df = pd.read_csv("data/pre_ESTER.csv", sep=";").WT
    
    plt.figure()
    plt.plot(df, label = 'pre- ‎€STER')
    
    new = probs_per_time / 5.1 - 0.6
    plt.plot(new, label = 'Realness score for pre trained discriminator')
    plt.title(r'pre- ‎€STER and its realness score')
    plt.ylabel(r'Short rate \tau')
    plt.xlabel(r'pre-ESTER days')
    plt.ylim((-0.57, -0.41))
    plt.legend()

    def to_probs(x):
            return (x + 0.6) * 5.1
        
    def to_pre_ester(x):
        return (x / 5.1) - 0.6
    
    ax = plt.gca()
    secaxy = ax.secondary_yaxis('right', functions = (to_probs, to_pre_ester))
    secaxy.set_ylabel(r'Realness score')    
    plt.show()
        
    return probs
