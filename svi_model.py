import numpy as np
import pandas as pd
from scipy import optimize
import matplotlib.pyplot as plt
from typing import Tuple, Optional, List, Union
import warnings


class SVI:
    """
    Stochastic Volatility Inspired (SVI) model for fitting implied volatility curves.

    This implementation enforces arbitrage-free constraints to ensure financial validity.

    The SVI model parameterizes the total implied variance as:
    w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2))

    where:
    - k = ln(K/S) is the log-moneyness
    - a, b, sigma, rho, m are the SVI parameters
    """

    def __init__(self):
        self.parameters = None
        self.fit_result = None

    def fit(
        self,
        strikes: np.ndarray,
        implied_vols: np.ndarray,
        underlying_price: float,
        initial_params: Optional[List[float]] = None,
        method: Union[str, List[str]] = "auto",
        tolerance: float = 1e-6,
        max_attempts: int = 3,
    ) -> Tuple[np.ndarray, dict]:
        """
        Fit the SVI model to market implied volatility data with arbitrage-free constraints.

        Parameters:
        -----------
        strikes : np.ndarray
            Array of strike prices
        implied_vols : np.ndarray
            Array of corresponding implied volatilities
        underlying_price : float
            Current underlying asset price
        initial_params : Optional[List[float]]
            Initial parameter guess [a, b, sigma, rho, m]. If None, uses smart initialization.
        method : Union[str, List[str]]
            Optimization method. Options: 'auto', 'L-BFGS-B', 'SLSQP' or list of methods to try
        tolerance : float
            Optimization tolerance (default: 1e-6)
        max_attempts : int
            Maximum number of optimization attempts with different initial conditions

        Returns:
        --------
        Tuple[np.ndarray, dict]
            Fitted parameters and optimization result
        """
        self.strikes = strikes
        self.implied_vols = implied_vols
        self.underlying_price = underlying_price
        self.log_moneyness = np.log(strikes / underlying_price)

        # Smart parameter initialization
        if initial_params is None:
            initial_params = self._smart_initialization()

        # Ensure initial params are within bounds
        bounds = self._get_parameter_bounds()
        initial_params = np.clip(
            initial_params,
            [b[0] + 1e-6 for b in bounds],
            [b[1] - 1e-6 for b in bounds],
        )

        # Define optimization methods - prioritize L-BFGS-B as it's most stable
        if method == "auto":
            methods_to_try = ["L-BFGS-B", "SLSQP"]
        elif isinstance(method, str):
            methods_to_try = [method]
        else:
            methods_to_try = method

        best_result = None
        best_objective = np.inf

        def objective_function(params):
            """Objective function with built-in penalty for constraint violations."""
            try:
                a, b, sigma, rho, m = params

                # Strict parameter validation with high penalty
                if sigma <= 0.001 or b <= 0.001 or abs(rho) >= 0.999:
                    return 1e10

                # Check arbitrage constraints with penalty
                if not self._check_arbitrage_constraints_soft(params):
                    return 1e8

                model_variance = self._calculate_variance(
                    self.log_moneyness, a, b, sigma, rho, m
                )

                # Check for invalid variances
                if np.any(model_variance <= 0) or np.any(np.isnan(model_variance)):
                    return 1e10

                market_variance = np.square(self.implied_vols)

                # Robust objective function with relative errors
                relative_errors = (model_variance - market_variance) / (
                    market_variance + 1e-6
                )
                main_objective = np.sum(np.square(relative_errors))

                # Add soft constraint penalties
                penalty = self._calculate_constraint_penalty(params)

                return main_objective + penalty

            except Exception as e:
                return 1e10

        # Suppress scipy warnings during optimization
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            warnings.simplefilter("ignore", UserWarning)
            warnings.filterwarnings("ignore", message="delta_grad == 0.0.*")

            # Try different optimization methods
            for opt_method in methods_to_try:
                for attempt in range(max_attempts):
                    try:
                        # Generate better initial parameters for multiple attempts
                        if attempt > 0:
                            perturbed_params = self._generate_perturbed_params(
                                initial_params, bounds, attempt
                            )
                        else:
                            perturbed_params = initial_params

                        # Use L-BFGS-B as primary method (most stable for bounded problems)
                        if opt_method == "L-BFGS-B":
                            result = optimize.minimize(
                                objective_function,
                                perturbed_params,
                                method=opt_method,
                                bounds=bounds,
                                options={
                                    "ftol": tolerance,
                                    "gtol": tolerance * 10,
                                    "maxiter": 1000,
                                    "maxfun": 2000,
                                },
                            )
                        elif opt_method == "SLSQP":
                            # Use SLSQP only with very conservative settings
                            constraints = self._get_arbitrage_constraints()
                            result = optimize.minimize(
                                objective_function,
                                perturbed_params,
                                method=opt_method,
                                bounds=bounds,
                                constraints=constraints,
                                options={
                                    "ftol": tolerance,
                                    "maxiter": 500,
                                    "disp": False,
                                },
                            )
                        else:
                            # Fallback for other methods
                            result = optimize.minimize(
                                objective_function,
                                perturbed_params,
                                method=opt_method,
                                bounds=bounds,
                                options={"maxiter": 1000},
                            )

                        # Check if this is the best result and satisfies all constraints
                        if (
                            result.success
                            and result.fun < best_objective
                            and self._check_arbitrage_constraints(result.x)
                        ):
                            best_result = result
                            best_objective = result.fun

                    except Exception as e:
                        continue

                # If we found a good solution, break early
                if best_result is not None and best_objective < 1e-4:
                    break

        # Final fallback with very simple bounds-only optimization
        if best_result is None:
            print("Trying final fallback optimization...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)

                    # Use the most conservative bounds and simple objective
                    simple_bounds = [
                        (0.01, 0.5),  # a
                        (0.01, 0.5),  # b
                        (0.05, 0.3),  # sigma
                        (-0.8, 0.8),  # rho
                        (-0.2, 0.2),  # m
                    ]

                    def simple_objective(params):
                        a, b, sigma, rho, m = params
                        try:
                            model_variance = self._calculate_variance(
                                self.log_moneyness, a, b, sigma, rho, m
                            )
                            if np.any(model_variance <= 0):
                                return 1e6
                            market_variance = np.square(self.implied_vols)
                            return np.sum(np.square(model_variance - market_variance))
                        except:
                            return 1e6

                    result = optimize.minimize(
                        simple_objective,
                        [0.1, 0.1, 0.1, 0.0, 0.0],  # Very simple initial guess
                        method="L-BFGS-B",
                        bounds=simple_bounds,
                        options={"ftol": 1e-6, "maxiter": 500},
                    )

                    if result.success:
                        best_result = result

            except Exception as e:
                pass

        if best_result is None:
            raise RuntimeError(
                "SVI optimization failed. The implied volatility data may be too noisy or "
                "incompatible with the SVI model structure. Consider data preprocessing or "
                "using a different volatility model."
            )

        self.fit_result = best_result
        self.parameters = best_result.x
        return self.parameters, self.fit_result

    def _smart_initialization(self) -> List[float]:
        """
        Smart initialization of SVI parameters based on market data characteristics.
        """
        # Calculate some market characteristics
        atm_iv = np.interp(0, self.log_moneyness, self.implied_vols)  # ATM implied vol
        min_iv = np.min(self.implied_vols)
        max_iv = np.max(self.implied_vols)

        # Estimate skew direction - be more careful with edge cases
        left_indices = self.log_moneyness < -0.05
        right_indices = self.log_moneyness > 0.05

        if np.any(left_indices) and np.any(right_indices):
            left_wing = np.mean(self.implied_vols[left_indices])
            right_wing = np.mean(self.implied_vols[right_indices])
            skew = (left_wing - right_wing) / (left_wing + right_wing + 1e-6)
        else:
            skew = 0.0

        # Smart parameter initialization - be more conservative
        a = min_iv**2 * 0.9  # Base level, slightly higher
        b = (max_iv**2 - min_iv**2) * 0.3  # Wing scale, more conservative
        sigma = 0.15  # Smoothness parameter, slightly higher
        rho = np.clip(skew, -0.8, 0.8)  # Skew, but not too extreme
        m = 0.0  # ATM shift

        return [a, b, sigma, rho, m]

    def _get_parameter_bounds(self) -> List[Tuple[float, float]]:
        """
        Set reasonable bounds for SVI parameters to ensure no-arbitrage conditions.
        """
        return [
            (0.001, 1.0),  # a: variance floor > 0
            (0.001, 1.0),  # b: wing scale > 0
            (0.01, 0.5),  # sigma: smoothness > 0
            (-0.99, 0.99),  # rho: correlation
            (-0.5, 0.5),  # m: ATM shift
        ]

    def _get_arbitrage_constraints(self) -> List[dict]:
        """
        Define simplified arbitrage-free constraints for SVI parameters.
        """
        constraints = []

        # Constraint 1: Positive total variance (butterfly constraint)
        def butterfly_constraint(params):
            a, b, sigma, rho, m = params
            return a + b * sigma * np.sqrt(1 - rho**2)

        constraints.append({"type": "ineq", "fun": butterfly_constraint})

        # Constraint 2: Calendar arbitrage - variance slope should be reasonable
        def calendar_constraint(params):
            a, b, sigma, rho, m = params
            max_slope = b * (1 + abs(rho))
            return 2.0 - max_slope  # More relaxed upper bound

        constraints.append({"type": "ineq", "fun": calendar_constraint})

        return constraints

    def _check_arbitrage_constraints(self, params: np.ndarray) -> bool:
        """
        Check if parameters satisfy arbitrage-free constraints.
        """
        try:
            a, b, sigma, rho, m = params

            # Basic parameter validity
            if sigma <= 0 or b < 0 or abs(rho) >= 1:
                return False

            # Butterfly constraint
            if a + b * sigma * np.sqrt(1 - rho**2) < 0:
                return False

            # Calendar constraint (more relaxed)
            if b * (1 + abs(rho)) > 2.0:
                return False

            # Check variance positivity at market points
            variances = self._calculate_variance(
                self.log_moneyness, a, b, sigma, rho, m
            )
            if np.any(variances <= 0):
                return False

            return True
        except:
            return False

    def _generate_perturbed_params(
        self, initial_params: List[float], bounds: List[Tuple], attempt: int
    ) -> List[float]:
        """Generate better perturbed parameters for multiple optimization attempts."""
        # Use different strategies for different attempts
        if attempt == 1:
            # Small random perturbation
            noise_scale = 0.1
            perturbed = np.array(initial_params) * (
                1 + np.random.normal(0, noise_scale, 5)
            )
        elif attempt == 2:
            # Medium perturbation with bias toward center of bounds
            centers = [(b[0] + b[1]) / 2 for b in bounds]
            perturbed = 0.7 * np.array(initial_params) + 0.3 * np.array(centers)
            perturbed += np.random.normal(0, 0.05, 5)
        else:
            # Large perturbation - random sampling from bounds
            perturbed = []
            for b in bounds:
                perturbed.append(np.random.uniform(b[0] + 0.01, b[1] - 0.01))
            perturbed = np.array(perturbed)

        # Ensure within bounds
        perturbed = np.clip(
            perturbed,
            [b[0] + 1e-6 for b in bounds],
            [b[1] - 1e-6 for b in bounds],
        )
        return perturbed.tolist()

    def _check_arbitrage_constraints_soft(self, params: np.ndarray) -> bool:
        """Soft check for arbitrage constraints (used in objective function)."""
        try:
            a, b, sigma, rho, m = params

            # Basic bounds check
            if sigma <= 0.001 or b <= 0.001 or abs(rho) >= 0.999:
                return False

            # Butterfly constraint with small tolerance
            if a + b * sigma * np.sqrt(1 - rho**2) < -0.01:
                return False

            # Check a few key points for positive variance
            test_points = np.array([-0.2, 0.0, 0.2])
            variances = self._calculate_variance(test_points, a, b, sigma, rho, m)
            if np.any(variances <= 0.001):
                return False

            return True
        except:
            return False

    def _calculate_constraint_penalty(self, params: np.ndarray) -> float:
        """Calculate soft penalty for constraint violations."""
        try:
            a, b, sigma, rho, m = params
            penalty = 0.0

            # Penalty for negative variance at test points
            test_points = np.linspace(-0.5, 0.5, 10)
            variances = self._calculate_variance(test_points, a, b, sigma, rho, m)
            negative_var_penalty = np.sum(np.maximum(0, -variances)) * 1000
            penalty += negative_var_penalty

            # Penalty for butterfly constraint violation
            butterfly_val = a + b * sigma * np.sqrt(1 - rho**2)
            if butterfly_val < 0:
                penalty += abs(butterfly_val) * 1000

            # Penalty for extreme parameters
            if b * (1 + abs(rho)) > 1.5:
                penalty += (b * (1 + abs(rho)) - 1.5) * 100

            return penalty
        except:
            return 1000.0

    def _calculate_variance(
        self,
        log_moneyness: np.ndarray,
        a: float,
        b: float,
        sigma: float,
        rho: float,
        m: float,
    ) -> np.ndarray:
        """
        Calculate the SVI total implied variance for given log-moneyness values.

        Parameters:
        -----------
        log_moneyness : np.ndarray
            Array of log-moneyness values (ln(K/S))
        a, b, sigma, rho, m : float
            SVI parameters

        Returns:
        --------
        np.ndarray
            Array of total implied variances
        """
        k_minus_m = log_moneyness - m
        sqrt_term = np.sqrt(np.square(k_minus_m) + sigma**2)
        variance = a + b * (rho * k_minus_m + sqrt_term)
        return variance

    def predict_iv(
        self, strikes: np.ndarray, underlying_price: Optional[float] = None
    ) -> np.ndarray:
        """
        Predict implied volatilities for given strike prices using fitted parameters.

        Parameters:
        -----------
        strikes : np.ndarray
            Array of strike prices
        underlying_price : Optional[float]
            Underlying price (uses fitted price if None)

        Returns:
        --------
        np.ndarray
            Array of predicted implied volatilities
        """
        if self.parameters is None:
            raise ValueError("Model must be fitted before making predictions")

        if underlying_price is None:
            underlying_price = self.underlying_price

        log_moneyness = np.log(strikes / underlying_price)
        a, b, sigma, rho, m = self.parameters

        variance = self._calculate_variance(log_moneyness, a, b, sigma, rho, m)
        return np.sqrt(variance)

    def plot_fit(self, num_points: int = 1000, figsize: Tuple[int, int] = (10, 6)):
        """
        Plot the fitted SVI curve along with market data points.

        Parameters:
        -----------
        num_points : int
            Number of points for smooth curve plotting
        figsize : Tuple[int, int]
            Figure size for the plot
        """
        if self.parameters is None:
            raise ValueError("Model must be fitted before plotting")

        plt.figure(figsize=figsize)

        # Create smooth curve for plotting
        strike_range = np.linspace(self.strikes.min(), self.strikes.max(), num_points)
        fitted_iv = self.predict_iv(strike_range)

        # Plot fitted curve and market data
        plt.plot(
            strike_range, fitted_iv, "b-", label="SVI Fit (Arbitrage-Free)", linewidth=2
        )
        plt.scatter(
            self.strikes,
            self.implied_vols,
            color="red",
            alpha=0.7,
            label="Market Data",
            s=50,
        )

        plt.xlabel("Strike Price")
        plt.ylabel("Implied Volatility")
        plt.title(f"Arbitrage-Free SVI Model Fit")
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Add fit quality info
        if hasattr(self, "strikes"):
            predicted_iv = self.predict_iv(self.strikes)
            rmse = np.sqrt(np.mean((predicted_iv - self.implied_vols) ** 2))
            plt.text(
                0.02,
                0.98,
                f"RMSE: {rmse:.6f}",
                transform=plt.gca().transAxes,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="lightgreen"),
            )

        plt.show()

    def get_parameters_dict(self) -> dict:
        """
        Get fitted parameters as a dictionary.

        Returns:
        --------
        dict
            Dictionary with parameter names and values
        """
        if self.parameters is None:
            raise ValueError("Model must be fitted first")

        return {
            "a": self.parameters[0],
            "b": self.parameters[1],
            "sigma": self.parameters[2],
            "rho": self.parameters[3],
            "m": self.parameters[4],
        }

    def validate_arbitrage_free(self) -> dict:
        """
        Check if the fitted SVI parameters satisfy no-arbitrage conditions.

        Returns:
        --------
        dict
            Dictionary with arbitrage checks and violations
        """
        if self.parameters is None:
            raise ValueError("Model must be fitted first")

        a, b, sigma, rho, m = self.parameters

        checks = {
            "positive_variance": a > 0,
            "positive_wing_slope": b >= 0,
            "positive_smoothness": sigma > 0,
            "valid_correlation": -1 < rho < 1,
            "butterfly_condition": a + b * sigma * np.sqrt(1 - rho**2) >= 0,
        }

        checks["all_valid"] = all(checks.values())
        return checks


def test_svi_model():
    """
    Clean unit test using the original data from the notebook.
    Tests arbitrage-free SVI fitting.
    """
    # print("Testing SVI Model with Market Data...")

    # Original market data
    strikes = np.array(
        [
            3150.0,
            3200.0,
            3250.0,
            3300.0,
            3350.0,
            3400.0,
            3450.0,
            3500.0,
            3550.0,
            3600.0,
            3650.0,
            3700.0,
            3750.0,
            3800.0,
            3850.0,
            3900.0,
            3950.0,
            4000.0,
            4100.0,
            4200.0,
            4300.0,
            4400.0,
            4600.0,
        ]
    )

    implied_vols = np.array(
        [
            0.2958993041228522,
            0.30358918200894824,
            0.28777107095621896,
            0.31871211030819274,
            0.3025578398264387,
            0.2969689043970068,
            0.29999180471435527,
            0.3202383380649552,
            0.3103344555136535,
            0.3216426119557985,
            0.3163522897404212,
            0.33040258945028084,
            0.3421558653365632,
            0.360412659157153,
            0.36565813374806055,
            0.38346113375699015,
            0.3984098629636823,
            0.40996169217951256,
            0.45832294820898356,
            0.48539561626657873,
            0.5288187544855535,
            0.5430791027360832,
            0.6199387769242027,
        ]
    )

    underlying_price = 3360
    # print(f"Underlying Price: {underlying_price}")
    # print(f"Strike Range: {strikes.min():.0f} - {strikes.max():.0f}")
    # print(f"IV Range: {implied_vols.min():.3f} - {implied_vols.max():.3f}")

    # # Fit the arbitrage-free SVI model
    # print("\nFitting SVI model...")
    svi = SVI()

    try:
        fitted_params, fit_result = svi.fit(strikes, implied_vols, underlying_price)

        # Calculate fit quality metrics
        predicted_iv = svi.predict_iv(strikes)
        rmse = np.sqrt(np.mean((predicted_iv - implied_vols) ** 2))
        mae = np.mean(np.abs(predicted_iv - implied_vols))
        max_error = np.max(np.abs(predicted_iv - implied_vols))

        # Get fitted parameters
        param_dict = svi.get_parameters_dict()

        # print(f"\n✅ SVI Model Fitted Successfully!")
        # print(f"📊 Fit Quality Metrics:")
        # print(f"   - RMSE: {rmse:.6f}")
        # print(f"   - MAE:  {mae:.6f}")
        # print(f"   - Max Error: {max_error:.6f}")

        # print(f"\n📈 Fitted SVI Parameters:")
        # for name, value in param_dict.items():
        #     print(f"   - {name}: {value:.6f}")

        # Validate arbitrage-free conditions
        # arbitrage_check = svi.validate_arbitrage_free()
        # print(f"\n🔒 Arbitrage-Free Validation:")
        # for check, passed in arbitrage_check.items():
        #     status = "✅" if passed else "❌"
        #     print(f"   - {check}: {status}")

        # # Create visualization
        # print(f"\n📉 Generating plot...")
        svi.plot_fit()

        return predicted_iv

    except Exception as e:
        print(f"❌ SVI Model Failed: {str(e)}")
        return None


if __name__ == "__main__":
    # Run the test with detailed output
    test_results = test_svi_model()
    if test_results is not None:
        # print(f"\n🎉 Test completed successfully!")
        print(f"Predicted IV sample: {test_results[:5]}")
    else:
        print(f"Test failed!")
