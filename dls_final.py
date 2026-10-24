import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import math
import sys

# ==========================================
# 1. DATA LOADING AND CLEANING
# ==========================================
def load_and_clean_data(filepath):
    """
    Loads the DLS resource data.
    Expected format: Index (Overs Remaining) vs Columns (Wickets Lost 0-9).
    """
    print("Loading DLS resource table...")
    try:
        df = pd.read_csv(filepath)
        
        # Standardize column names: The first column usually represents Overs Remaining
        if 'balls' in df.columns:
            df.rename(columns={'balls': 'overs_remaining'}, inplace=True)
        elif 'overs' in df.columns:
            df.rename(columns={'overs': 'overs_remaining'}, inplace=True)
            
        df.set_index('overs_remaining', inplace=True)
        df = df.apply(pd.to_numeric, errors='coerce')
        df.sort_index(ascending=True, inplace=True) # Ensure index is sorted for interpolation
        
        print("Data loaded successfully.")
        return df
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        return None

# ==========================================
# 2. VISUALIZATION
# ==========================================
def plot_resource_curves(df):
    """
    Plots the resource curves for visual analysis.
    """
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")

    wickets_to_plot = ['0', '2', '5', '9']
    available_cols = [w for w in wickets_to_plot if w in df.columns]

    for w in available_cols:
        sns.lineplot(x=df.index, y=df[w], label=f"{w} Wickets Down", linewidth=2)

    plt.title("DLS Resource Depletion Curve")
    plt.xlabel("Overs Remaining")
    plt.ylabel("Resource %")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig('dls_resource_curve.png')
    print("Chart saved as 'dls_resource_curve.png'")

# ==========================================
# 3. ADVANCED DLS CALCULATOR
# ==========================================
class DLSCalculator:
    def __init__(self, resource_df):
        self.table = resource_df
        self.max_overs = self.table.index.max()

    def get_resource_percent(self, overs_remaining, wickets_lost):
        """
        Returns resource percentage using Linear Interpolation for fractional overs.
        """
        # 1. Boundaries
        if wickets_lost >= 10: return 0.0
        if overs_remaining <= 0: return 0.0
        if overs_remaining > self.max_overs: overs_remaining = self.max_overs
        
        # 2. Exact match check
        lower_over = math.floor(overs_remaining)
        upper_over = math.ceil(overs_remaining)
        
        # Get values from table (converting wickets to string column name)
        w_col = str(wickets_lost)
        if w_col not in self.table.columns: return 0.0

        val_lower = self.table.loc[lower_over, w_col] if lower_over in self.table.index else 0.0
        val_upper = self.table.loc[upper_over, w_col] if upper_over in self.table.index else 0.0
        
        if lower_over == upper_over:
            return val_lower
            
        # 3. Linear Interpolation
        # Fraction of the over remaining (e.g., 15.2 -> 0.2)
        fraction = overs_remaining - lower_over
        interpolated_value = val_lower + (val_upper - val_lower) * fraction
        return interpolated_value

    def calculate_team_resources(self, total_scheduled_overs, overs_played, wickets_lost, interruption_data=None):
        """
        Calculates the final Resource Percentage (R) available to a team.
        
        Logic:
        Start Resources (based on scheduled overs)
        MINUS Resources lost due to interruptions (if any)
        MINUS Resources lost due to premature termination (e.g., All Out or Rain ending innings)
        """
        # 1. Start with resources for the originally scheduled overs (0 wickets down)
        start_res = self.get_resource_percent(total_scheduled_overs, 0)
        
        # 2. Handle Interruptions (if implemented specific logic needed)
        # For this simplified version, we calculate based on 'Resources Consumed' vs 'Resources Denied'
        # But standard DLS often uses: R_final = R_start - R_lost_during_break
        
        current_res = start_res
        
        if interruption_data:
            # interruption_data = {'overs_at_stop': X, 'wickets_at_stop': Y, 'new_total_overs': Z}
            # Resources Lost = Res(Overs Left Before, Wkts) - Res(Overs Left After, Wkts)
            overs_left_before = total_scheduled_overs - interruption_data['overs_at_stop']
            overs_left_after = interruption_data['new_total_overs'] - interruption_data['overs_at_stop']
            
            r_before = self.get_resource_percent(overs_left_before, interruption_data['wickets_at_stop'])
            r_after = self.get_resource_percent(overs_left_after, interruption_data['wickets_at_stop'])
            
            lost_resource = r_before - r_after
            current_res -= lost_resource

        return current_res

# ==========================================
# 4. INPUT HELPERS
# ==========================================
def get_input(prompt, type_func, min_val=None, max_val=None):
    while True:
        try:
            val = type_func(input(prompt))
            if min_val is not None and val < min_val:
                print(f"Value must be at least {min_val}")
                continue
            if max_val is not None and val > max_val:
                print(f"Value must be at most {max_val}")
                continue
            return val
        except ValueError:
            print("Invalid input. Please try again.")

# ==========================================
# 5. MAIN APP LOGIC
# ==========================================
def run_advanced_scenario(calc):
    print("\n" + "="*50)
    print("   ADVANCED DLS SCENARIO CALCULATOR")
    print("="*50)

    # --- TEAM 1 INPUTS ---
    print("\n--- TEAM 1 INNINGS ---")
    t1_score = get_input("Enter Team 1 Final Score: ", int, 0)
    t1_overs_scheduled = get_input("Team 1 Scheduled Overs (e.g., 20): ", int, 5, 50)
    
    # Did they play full overs?
    t1_completed = input("Did Team 1 play their full quota of overs (or get All Out)? (y/n): ").lower()
    
    r1 = 0.0
    if t1_completed == 'y':
        # If they played full overs (or all out), they used the full resource allocated to them
        r1 = calc.get_resource_percent(t1_overs_scheduled, 0)
    else:
        # TERMINATION CASE: E.g. Rain stopped play at 18.2 overs
        print("   >> Case: Innings Terminated Early")
        t1_overs_played = get_input("   Overs played when innings ended (e.g. 18.2): ", float, 0, t1_overs_scheduled)
        t1_wickets = get_input("   Wickets lost: ", int, 0, 10)
        
        # Resources Used = Total Available - Resources Remaining at termination
        res_total = calc.get_resource_percent(t1_overs_scheduled, 0)
        overs_remaining = t1_overs_scheduled - t1_overs_played
        res_remaining = calc.get_resource_percent(overs_remaining, t1_wickets)
        r1 = res_total - res_remaining

    print(f"-> Team 1 Resource Usage (R1): {r1:.2f}%")

    # --- TEAM 2 INPUTS ---
    print("\n--- TEAM 2 INNINGS ---")
    t2_overs_orig = get_input("Team 2 Original Scheduled Overs (e.g. 20): ", int, 5, 50)
    
    interrupted = input("Was Team 2's innings interrupted/reduced AFTER it started? (y/n): ").lower()
    
    r2 = 0.0
    if interrupted != 'y':
        # Simple reduction before start or no reduction
        t2_overs_avail = get_input("How many overs does Team 2 actually have to bat? ", float, 0, 50)
        r2 = calc.get_resource_percent(t2_overs_avail, 0)
    else:
        # INTERRUPTION CASE: The logic from dls.py
        print("   >> Case: Interruption during play")
        t2_played = get_input("   Overs played at interruption: ", float, 0, t2_overs_orig)
        t2_wkts = get_input("   Wickets lost at interruption: ", int, 0, 10)
        t2_new_total = get_input(f"   Team 2's NEW total overs (was {t2_overs_orig}): ", float, t2_played, 50)
        
        # Calculate R2 using the loss method
        # Start with full original resources
        res_start = calc.get_resource_percent(t2_overs_orig, 0)
        
        # Calculate Resource Lost during rain break
        # Lost = Res(Overs Remaining Before, Wkts) - Res(Overs Remaining After, Wkts)
        overs_left_before = t2_overs_orig - t2_played
        overs_left_after = t2_new_total - t2_played
        
        res_at_stop = calc.get_resource_percent(overs_left_before, t2_wkts)
        res_at_resume = calc.get_resource_percent(overs_left_after, t2_wkts)
        
        res_lost = res_at_stop - res_at_resume
        r2 = res_start - res_lost
        print(f"   (Debug: Resources Lost due to rain = {res_lost:.2f}%)")

    print(f"-> Team 2 Resources Available (R2): {r2:.2f}%")

    # --- FINAL CALCULATION ---
    print("\n" + "-"*30)
    print("CALCULATION RESULT")
    
    if r2 == 0:
        print("Error: Team 2 has 0 resources (Game abandoned?)")
    else:
        # Standard DLS Formula: Target = S * (R2/R1)
        par_score = t1_score * (r2 / r1)
        target = int(par_score) + 1
        
        print(f"Team 1 Score: {t1_score}")
        print(f"R1 (Team 1): {r1:.2f}%")
        print(f"R2 (Team 2): {r2:.2f}%")
        print(f"Par Score: {par_score:.2f}")
        print(f"WINNING TARGET: {target}")
    print("-"*30)

if __name__ == "__main__":
    csv_file = 'dls_resource_data_for_t20s.csv'
    df = load_and_clean_data(csv_file)
    
    if df is not None:
        plot_resource_curves(df)
        calculator = DLSCalculator(df)
        
        while True:
            run_advanced_scenario(calculator)
            again = input("\nCalculate another scenario? (y/n): ").lower()
            if again != 'y':
                break