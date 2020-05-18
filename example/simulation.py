#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path
from covsirphy import Simulator, Estimator, SIRF


def main():
    # Create output directory in example directory
    code_path = Path(__file__)
    output_dir = code_path.with_name("output").joinpath(code_path.stem)
    output_dir.mkdir(exist_ok=True, parents=True)
    # Simulation
    eg_population = 1_000_000
    simulator = Simulator(country="Example", province="Example-1")
    simulator.add(
        model=SIRF, step_n=180, population=eg_population,
        param_dict={
            "theta": 0.002, "kappa": 0.005, "rho": 0.2, "sigma": 0.075
        },
        y0_dict={"x": 0.999, "y": 0.001, "z": 0, "w": 0}
    )
    simulator.run()
    # Non-dimensional
    nondim_df = simulator.non_dim()
    nondim_df.to_csv(output_dir.joinpath("non_dim.csv"), index=False)
    # Non-dimensional
    dim_df = simulator.dim(tau=1440, start_date="22Jan2020")
    dim_df.to_csv(output_dir.joinpath("dim.csv"), index=False)
    # Hyperparameter estimation of example data
    estimator = Estimator(
        clean_df=dim_df, model=SIRF, population=eg_population,
        country="Example", province="Example-1"
    )
    estimator.run(n_trials=500)
    estimated_df = estimator.result("SIR-F")
    estimated_df.to_csv(output_dir.joinpath("estimated.csv"), index=True)


if __name__ == "__main__":
    main()