#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
from covsirphy.cleaning.term import Term
from covsirphy.ode.mbase import ModelBase
from covsirphy.simulation.estimator import Estimator
from covsirphy.simulation.simulator import ODESimulator


class PhaseUnit(Term):
    """
    Save information of  a phase.

    Args:
        start_date (str): start date of the phase
        end_date (str): end date of the phase
        population (int): population value
    """

    def __init__(self, start_date, end_date, population):
        start = self.date_obj(start_date)
        end = self.date_obj(end_date)
        if start >= end:
            raise ValueError(
                f"@end_date ({end_date}) must be over @start_date ({start_date}).")
        self.start_date = start_date
        self.end_date = end_date
        self.population = self.ensure_natural_int(
            population, name="population")
        # Summary of information
        self.info_dict = {
            self.START: start_date,
            self.END: end_date,
            self.N: population,
            self.ODE: None,
            self.RT: None
        }
        self.ode_dict = {self.TAU: None}
        self.day_param_dict = {}
        self.est_dict = {
            self.RMSLE: None,
            self.TRIALS: None,
            self.RUNTIME: None
        }
        # Init
        self.model = None
        self.y0_dict = {}

    def to_dict(self):
        """
        Summarize phase information and return as a dictionary.

        Returns:
            dict:
                - Start: start date of the phase
                - End: end date of the phase
                - Population: population value of the start date
                - if available:
                    - ODE: model name
                    - Rt: (basic) reproduction number
                    - parameter values if available
                    - day parameter values if available
                    - tau: tau value [min]
                    - RMSLE: RMSLE value of estimation
                    - Trials: the number of trials in estimation
                    - Runtime: runtime of estimation
        """
        summary_dict = self.info_dict.copy()
        summary_dict.update(self.ode_dict)
        summary_dict.update(self.day_param_dict)
        summary_dict.update(self.est_dict)
        return summary_dict

    def summary(self):
        """
        Summarize information.

        Returns:
            pandas.DataFrame:
                Index:
                    reset index
                Columns:
                    - Start: start date of the phase
                    - End: end date of the phase
                    - Population: population value of the start date
                    - if available:
                        - ODE: model name
                        - Rt: (basic) reproduction number
                        - parameter values if available
                        - tau: tau value [min]
                        - day parameter values if available
                        - RMSLE: RMSLE value of estimation
                        - Trials: the number of trials in estimation
                        - Runtime: runtime of estimation
        """
        summary_dict = self.to_dict()
        df = pd.DataFrame(summary_dict, orient="index")
        return df.dropna(how="all", axis=1)

    def set_ode(self, model, tau=None, **kwargs):
        """
        Set ODE model, tau value and parameter values, if necessary.

        Args:
            model (covsirphy.ModelBase): ODE model
            tau (int or None): tau value [min], a divisor of 1440
        """
        # Model
        self.ensure_subclass(model, ModelBase, name="model")
        self.info_dict[self.ODE] = model.NAME
        # Parameter values
        ode_dict = dict.fromkeys(model.PARAMETERS, value=None)
        applied_dict = {k: v for (k, v) in kwargs.items() if k in ode_dict}
        ode_dict.update(applied_dict)
        ode_dict[self.TAU] = self.ensure_tau(tau)
        self.ode_dict = ode_dict

    def estimate(self, record_df, **kwargs):
        """
        Perform parameter estimation.

        Args:
            record_df (pandas.DataFrame)
                Index:
                    reset index
                Columns:
                    - Date (pd.TimeStamp): Observation date
                    - Confirmed (int): the number of confirmed cases
                    - Infected (int): the number of currently infected cases
                    - Fatal (int): the number of fatal cases
                    - Recovered (int): the number of recovered cases
                    - any other columns will be ignored
            **kwargs: keyword arguments of Estimator.run()
        """
        if self.model is None:
            raise ValueError(
                "PhaseUnit.set_ode(model) must be done in advance.")
        # Records
        self.ensure_dataframe(
            record_df, name="record_df", columns=self.NLOC_COLUMNS)
        # Parameter estimation of ODE model
        estimator = Estimator(
            record_df, self.model, self.population, **self.ode_dict)
        estimator.run(**kwargs)
        # Reproduction number
        est_dict = estimator.summary().to_dict()
        self.info_dict[self.RT] = est_dict.pop(self.RT)
        # Get parameter values and tau value
        ode_dict = {
            k: v for (k, v) in est_dict.items() if k in self.ode_dict}
        self.ode_dict.update(ode_dict)
        # Other information of estimation
        other_dict = dict(est_dict.items() - ode_dict.items())
        self.est_dict.update(other_dict)
        # Initial values
        tau = ode_dict[self.TAU]
        taufree_df = self.model.tau_free(record_df, self.population, tau=tau)
        var_set = set(self.model.VARIABLES)
        self.y0_dict = {
            k: v for (k, v) in taufree_df.iloc[0].to_dict() if k in var_set
        }

    def simulate(self):
        """
        Perform simulation with the set/estimated parameter values.

        Returns:
            pandas.DataFrame
                Index:
                    reset index
                Columns:
                    - Date (pd.TimeStamp): Observation date
                    - Confirmed (int): the number of confirmed cases
                    - Infected (int): the number of currently infected cases
                    - Fatal (int): the number of fatal cases
                    - Recovered (int): the number of recovered cases
        """
        param_dict = self.ode_dict.copy()
        tau = param_dict.pop(param_dict)
        # Simulation
        simulator = ODESimulator()
        simulator.add(
            model=self.model,
            step_n=self.days(self.start_date, self.end_date),
            population=self.population,
            param_dict=param_dict,
            y0_dict=self.y0_dict
        )
        simulator.run()
        # Return dimensionalized values
        df = simulator.dim(tau=tau, start_date=self.start_date)
        df = self.model.restore(df)
        return df.loc[:, self.NLOC_COLUMNS]
