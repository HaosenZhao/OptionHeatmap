import numpy as np
import pandas as pd
from typing import List, Tuple, Optional


class VIXCalculator:
    """
    VIX Calculator using standard CBOE VIX methodology.

    The VIX is calculated using out-of-the-money (OTM) options to measure
    the market's expectation of 30-day volatility.
    """

    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize VIX calculator.

        Parameters:
        -----------
        risk_free_rate : float
            Risk-free interest rate (default: 2%)
        """
        self.risk_free_rate = risk_free_rate
        self.strikes = None
        self.call_prices = None
        self.put_prices = None
        self.time_to_expiry = None
        self.forward_price = None
        self.atm_strike = None

    def calculate_vix(
        self,
        strikes: List[float],
        call_prices: List[float],
        put_prices: List[float],
        time_to_expiry: float,
        underlying_price: float,
    ) -> float:
        """
        Calculate VIX using standard CBOE methodology.

        Parameters:
        -----------
        strikes : List[float]
            List of strike prices
        call_prices : List[float]
            List of call option prices corresponding to strikes
        put_prices : List[float]
            List of put option prices corresponding to strikes
        time_to_expiry : float
            Time to expiry in years
        underlying_price : float
            Current underlying asset price

        Returns:
        --------
        float
            VIX value (annualized volatility percentage)
        """
        # Convert to numpy arrays and store
        self.strikes = np.array(strikes)
        self.call_prices = np.array(call_prices)
        self.put_prices = np.array(put_prices)
        self.time_to_expiry = time_to_expiry

        # Step 1: Calculate forward price using put-call parity
        self.forward_price = self._calculate_forward_price(underlying_price)

        # Step 2: Find at-the-money strike (closest to forward price)
        self.atm_strike = self._find_atm_strike()

        # Step 3: Select out-of-the-money options
        otm_contributions = self._calculate_otm_contributions()

        # Step 4: Calculate VIX
        variance = self._calculate_variance(otm_contributions)
        vix = np.sqrt(variance) * 100  # Convert to percentage

        return vix

    def _calculate_forward_price(self, underlying_price: float) -> float:
        """
        Calculate forward price using put-call parity.
        F = Strike + e^(rT) * (Call - Put)
        """
        # Find strikes where both call and put prices are available
        valid_mask = (self.call_prices > 0) & (self.put_prices > 0)
        valid_strikes = self.strikes[valid_mask]
        valid_calls = self.call_prices[valid_mask]
        valid_puts = self.put_prices[valid_mask]

        if len(valid_strikes) == 0:
            return underlying_price

        # Calculate forward prices for each valid strike
        forward_prices = valid_strikes + np.exp(
            self.risk_free_rate * self.time_to_expiry
        ) * (valid_calls - valid_puts)

        # Use the forward price from the strike closest to current underlying price
        closest_idx = np.argmin(np.abs(valid_strikes - underlying_price))
        return forward_prices[closest_idx]

    def _find_atm_strike(self) -> float:
        """
        Find the at-the-money strike (strike immediately below forward price).
        """
        below_forward = self.strikes[self.strikes <= self.forward_price]
        if len(below_forward) == 0:
            return self.strikes[0]
        return below_forward[-1]  # Highest strike below forward price

    def _calculate_otm_contributions(self) -> np.ndarray:
        """
        Calculate contributions from out-of-the-money options.
        """
        contributions = np.zeros(len(self.strikes))

        for i, strike in enumerate(self.strikes):
            # Skip if no valid price data
            if self.call_prices[i] <= 0 and self.put_prices[i] <= 0:
                continue

            # Calculate delta K (strike interval)
            delta_k = self._calculate_delta_k(i)

            # Select appropriate option price
            if strike < self.atm_strike:
                # Use put for strikes below ATM
                option_price = self.put_prices[i] if self.put_prices[i] > 0 else 0
            elif strike > self.atm_strike:
                # Use call for strikes above ATM
                option_price = self.call_prices[i] if self.call_prices[i] > 0 else 0
            else:
                # Use average of call and put for ATM strike
                call_price = self.call_prices[i] if self.call_prices[i] > 0 else 0
                put_price = self.put_prices[i] if self.put_prices[i] > 0 else 0
                if call_price > 0 and put_price > 0:
                    option_price = (call_price + put_price) / 2
                elif call_price > 0:
                    option_price = call_price
                else:
                    option_price = put_price

            # Calculate contribution: (ΔK/K²) * e^(rT) * Q(K)
            if option_price > 0 and strike > 0:
                contributions[i] = (
                    (delta_k / (strike**2))
                    * np.exp(self.risk_free_rate * self.time_to_expiry)
                    * option_price
                )

        return contributions

    def _calculate_delta_k(self, i: int) -> float:
        """
        Calculate the strike interval ΔK for strike i.
        """
        n_strikes = len(self.strikes)

        if i == 0:
            # First strike: use interval to next strike
            return self.strikes[1] - self.strikes[0]
        elif i == n_strikes - 1:
            # Last strike: use interval from previous strike
            return self.strikes[-1] - self.strikes[-2]
        else:
            # Middle strikes: use average of intervals on both sides
            return (self.strikes[i + 1] - self.strikes[i - 1]) / 2

    def _calculate_variance(self, contributions: np.ndarray) -> float:
        """
        Calculate the final variance using VIX formula.
        σ² = (2/T) * Σ(ΔK/K² * e^(rT) * Q(K)) - (1/T) * (F/K₀ - 1)²
        """
        # Sum all option contributions
        sigma_squared = (2 / self.time_to_expiry) * np.sum(contributions)

        # Subtract the forward term
        forward_term = (1 / self.time_to_expiry) * (
            (self.forward_price / self.atm_strike) - 1
        ) ** 2
        sigma_squared -= forward_term

        return max(sigma_squared, 0)  # Ensure non-negative variance


def test_vix_calculator():
    """
    Test the VIX calculator with sample data.
    """
    # Sample data
    strikes = [
        3150,
        3200,
        3250,
        3300,
        3350,
        3400,
        3450,
        3500,
        3550,
        3600,
        3650,
        3700,
        3750,
        3800,
        3850,
        3900,
        3950,
        4000,
        4100,
        4200,
        4300,
        4400,
        4600,
    ]
    call_prices = [
        210,
        165,
        125,
        92,
        65,
        44,
        28,
        17,
        10,
        6,
        3.5,
        2,
        1.2,
        0.7,
        0.4,
        0.2,
        0.1,
        0.05,
        0.01,
        0.005,
        0.002,
        0.001,
        0,
    ]
    put_prices = [
        0.5,
        1.2,
        2.5,
        5,
        9,
        15,
        24,
        36,
        52,
        71,
        93,
        118,
        146,
        177,
        211,
        248,
        288,
        331,
        422,
        521,
        628,
        743,
        998,
    ]

    time_to_expiry = 30 / 365  # 30 days in years
    underlying_price = 3360

    # Initialize and calculate VIX
    vix_calc = VIXCalculator()
    vix_value = vix_calc.calculate_vix(
        strikes, call_prices, put_prices, time_to_expiry, underlying_price
    )

    print(f"Calculated VIX: {vix_value:.2f}")
    print(f"Forward Price: {vix_calc.forward_price:.2f}")
    print(f"ATM Strike: {vix_calc.atm_strike:.0f}")

    return vix_value


if __name__ == "__main__":
    test_vix_calculator()
