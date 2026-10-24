import math
import pandas as pd

class DLSResourceTable:
    """
    Base class to hold and query a D/L resource table.
    
    The table is expected to be a 2D list: table[wickets_lost][overs_remaining]
    """
    def __init__(self, table, max_overs):
        self.resource_table = table
        self.max_overs = max_overs

    def get_resource_pct(self, overs_left, wickets_lost):
        """
        Gets the resource percentage from the table.
        
        Args:
            overs_left (int or float): Overs remaining. Can be fractional.
            wickets_lost (int): Wickets lost (0-9).
            
        Returns:
            float: The resource percentage.
        """
        if wickets_lost > 9:
            wickets_lost = 9
        if overs_left <= 0:
            return 0.0
        if overs_left > self.max_overs:
            overs_left = self.max_overs
            
        # Handle fractional overs by linear interpolation
        overs_floor = math.floor(overs_left)
        overs_ceil = math.ceil(overs_left)
        
        if overs_floor == overs_ceil:
            # It's a whole number
            return self.resource_table[wickets_lost][overs_floor]

        # Interpolate
        # Boundary checks are implicitly handled by capping overs_left at max_overs
        if overs_floor >= len(self.resource_table[0]):
            overs_floor = len(self.resource_table[0]) - 1

        resource_floor = self.resource_table[wickets_lost][overs_floor]
        resource_ceil = self.resource_table[wickets_lost][overs_ceil]
        
        fraction = overs_left - overs_floor
        return resource_floor + (resource_ceil - resource_floor) * fraction

class DLSTwenty20(DLSResourceTable):
    """
    Implements a D/L resource table for 20-over matches.
    This is NOT the official G20 table but a publicly available
    example for T20.
    """    
    _table = None # Initialize as None

    @classmethod
    def _load_table(cls):
        """Loads and transforms data from the T20 CSV file."""
        if cls._table is not None: # Avoid reloading if already loaded
            return cls._table

        try:
            df = pd.read_csv("dls_resource_data_for_t20s.csv")
            # The CSV is sorted from 20 down to 0. We need it sorted 0 up to 20 for list indexing.
            df_sorted = df.sort_values(by='balls', ascending=True)
            # The wicket columns in the CSV are named '0', '1', '2', etc.
            resource_cols = [str(w) for w in range(10)]
            # Transform the DataFrame into a list of lists: table[wickets][overs]
            cls._table = [df_sorted[col].tolist() for col in resource_cols]
            return cls._table
        except (FileNotFoundError, KeyError, IndexError) as e:
            # Raise a single, clear error for any loading/parsing issue
            raise RuntimeError(f"Failed to load or parse 'dls_resource_data_for_t20s.csv': {e}")

    def __init__(self):
        # Load the table on first instantiation
        table = self._load_table()
        super().__init__(table, max_overs=20)


class DLSCalculator:
    """
    Performs D/L calculations using a provided resource table.
    """
    def __init__(self, resource_table_obj: DLSResourceTable):
        self.rc = resource_table_obj

    def get_resources_used(self, total_overs, overs_played, wickets_lost):
        """
        Calculates the percentage of resources used by a team.
        """
        res_start = self.rc.get_resource_pct(total_overs, 0)
        
        overs_remaining = total_overs - overs_played
        if wickets_lost == 10:
             overs_remaining = 0 # All out means 0 resources remain
             
        res_end = self.rc.get_resource_pct(overs_remaining, wickets_lost)
        
        return res_start - res_end

    def calculate_target(self, team1_score, team1_total_overs, team1_overs_played, team1_wickets_lost, team2_total_overs):
        """
        Calculates the target for Team 2 (chasing team).
        
        Use this when Team 1's innings is complete (or interrupted) and
        Team 2's innings is about to begin with a set number of overs.
        
        Args:
            team1_score (int): Runs scored by Team 1.
            team1_total_overs (int): Overs scheduled for Team 1 at start.
            team1_overs_played (float): Overs faced by Team 1.
            team1_wickets_lost (int): Wickets lost by Team 1.
            team2_total_overs (int): Overs scheduled for Team 2.
            
        Returns:
            int: The target score for Team 2.
        """
        
        # Resources used by Team 1
        res_used_T1 = self.get_resources_used(team1_total_overs, team1_overs_played, team1_wickets_lost)
        
        # Resources available to Team 2
        res_avail_T2 = self.rc.get_resource_pct(team2_total_overs, 0)
        
        # Formula logic:
        # If T2 has fewer resources than T1 (res_avail_T2 < res_used_T1), 
        # T1's score is scaled down.
        # If T2 has more resources than T1 (res_avail_T2 > res_used_T1),
        # T1's score is scaled up.
        
        par_score = team1_score * (res_avail_T2 / res_used_T1)
        
        # G5.2: If Team 2 has more resources than Team 1, the target is not increased.
        if res_avail_T2 > res_used_T1:
            par_score = team1_score
        
        target = math.floor(par_score) + 1
        return int(target)

    def calculate_par_score(self, team1_score, team1_resources_used, team2_total_overs, team2_overs_played, team2_wickets_lost):
        """
        Calculates the par score for Team 2 at a specific point in
        their innings.
        
        Use this when Team 2's innings is interrupted by rain.
        If Team 2's score > par_score, they are winning.
        If Team 2's score == par_score, it's a tie.
        
        Args:
            team1_score (int): Runs scored by Team 1.
            team1_resources_used (float): Pre-calculated resources used by Team 1.
            team2_total_overs (int): Overs scheduled for Team 2 at start.
            team2_overs_played (float): Overs faced by Team 2.
            team2_wickets_lost (int): Wickets lost by Team 2.
            
        Returns:
            int: The par score at this point.
        """
        
        # Resources used by Team 2 *so far*
        res_used_T2 = self.get_resources_used(team2_total_overs, team2_overs_played, team2_wickets_lost)

        if team1_resources_used == 0:
            print("Error: Team 1 used 0 resources. Cannot calculate par score.")
            return -1

        # Par Score = (Team 1 Score * (T2 Resources Used / T1 Resources Used))
        par_score = team1_score * (res_used_T2 / team1_resources_used)
        
        # Apply G5.2 logic: If T2 has used more resources than T1, their par score should not be scaled up beyond T1's score.
        if res_used_T2 > team1_resources_used:
            par_score = team1_score

        return math.floor(par_score)

    def calculate_revised_target(self, team1_score, team1_resources_used,
                                 team2_total_overs_orig, team2_overs_at_stop, 
                                 team2_wickets_at_stop, team2_score_at_stop, 
                                 team2_total_overs_new):
        """
        Calculates a revised target when Team 2's innings is interrupted
        and then scheduled to resume with a new total over limit.
        
        Args:
            team1_score (int): Runs scored by Team 1.
            team1_resources_used (float): Pre-calculated resources used by Team 1.
            team2_total_overs_orig (int): Overs Team 2 had at the *start*.
            team2_overs_at_stop (float): Overs played by Team 2 at interruption.
            team2_wickets_at_stop (int): Wickets lost by Team 2 at interruption.
            team2_score_at_stop (int): Score of Team 2 at interruption.
            team2_total_overs_new (int): The *new* total overs T2 will play (e.g., 40).
            
        Returns:
            tuple: (new_target, runs_to_get, overs_remaining)
        """
        if team1_resources_used == 0:
            print("Error: Team 1 used 0 resources. Cannot calculate revised target.")
            return -1, -1, -1

        # 1. Resources used by T2 *before* the stop
        res_avail_T2_orig = self.rc.get_resource_pct(team2_total_overs_orig, 0)
        res_remain_T2_at_stop = self.rc.get_resource_pct(team2_total_overs_orig - team2_overs_at_stop, team2_wickets_at_stop)
        res_used_T2_at_stop = res_avail_T2_orig - res_remain_T2_at_stop
        
        # 2. Resources available to T2 *after* the stop (in their new, shorter innings)
        overs_remaining_new = team2_total_overs_new - team2_overs_at_stop
        if overs_remaining_new < 0:
            print("Error: New total overs is less than overs already played.")
            return -1, -1, -1
            
        res_avail_T2_at_restart = self.rc.get_resource_pct(overs_remaining_new, team2_wickets_at_stop)
        
        # 3. Total resources T2 will have in this new match
        res_total_T2_new = res_used_T2_at_stop + res_avail_T2_at_restart
        
        # 4. Calculate their new final "par score" based on these total resources
        par_score_T2_final = team1_score * (res_total_T2_new / team1_resources_used)
        
        # Apply G5.2 rule: If T2 has more resources, don't scale up T1's score.
        if res_total_T2_new > team1_resources_used:
            par_score_T2_final = team1_score

        new_target = math.floor(par_score_T2_final) + 1
        runs_to_get = new_target - team2_score_at_stop
        
        return int(new_target), int(runs_to_get), overs_remaining_new

# --- HELPER FUNCTIONS FOR USER INPUT ---

def get_int_input(prompt, min_val=None, max_val=None):
    """Gets validated integer input from the user."""
    while True:
        try:
            value_str = input(prompt)
            value_int = int(value_str)
            if min_val is not None and value_int < min_val:
                print(f"Error: Value must be at least {min_val}.")
            elif max_val is not None and value_int > max_val:
                print(f"Error: Value must be no more than {max_val}.")
            else:
                return value_int
        except ValueError:
            print("Error: Please enter a valid integer.")

def get_float_input(prompt, min_val=None, max_val=None):
    """Gets validated float input from the user (for overs)."""
    while True:
        try:
            value_str = input(prompt)
            value_float = float(value_str)
            if min_val is not None and value_float < min_val:
                print(f"Error: Value must be at least {min_val}.")
            elif max_val is not None and value_float > max_val:
                print(f"Error: Value must be no more than {max_val}.")
            else:
                # Check for valid over format (e.g., 6.5, 6.6 are invalid)
                if (value_float * 10) % 10 > 5:
                     print("Error: Invalid overs format. Max is .5 (e.g., 20.5).")
                else:
                    return value_float
        except ValueError:
            print("Error: Please enter a valid number (e.g., 30 or 20.5).")

def get_choice(prompt, choices):
    """Gets a choice from a list of valid string choices."""
    while True:
        choice = input(prompt).strip().upper()
        if choice in choices:
            return choice
        else:
            print(f"Error: Invalid choice. Please enter one of {choices}.")

# --- MAIN INTERACTIVE FUNCTION ---

def main():
    print("--- D/L T20 Calculator ---")
    
    try:
        # Default to T20 calculator
        calculator = DLSCalculator(DLSTwenty20())
    except RuntimeError as e:
        print(f"\nError initializing calculator: {e}")
        return
    max_overs = 20
    
    # 2. Choose Calculation Type with descriptions
    print("\nSelect a calculation type:")
    print("1: Calculate Target")
    print("   - Use when Team 2's innings is reduced *before* it starts (e.g., rain delay between innings).")
    print("2: Calculate Par Score")
    print("   - Use when Team 2's innings is interrupted, to determine which team is ahead if the match is abandoned.")
    print("3: Revise Target")
    print("   - Use when Team 2's innings is interrupted and will resume with a *new*, reduced number of total overs.")
    calc_type = get_choice("Enter your choice (1, 2, or 3): ", ["1", "2", "3"])
    
    print("\n--- Team 1 Innings (Batting First) ---")
    t1_score = get_int_input("Team 1 total score: ", min_val=0)
    t1_total_overs = get_int_input(f"Team 1 scheduled overs (e.g., {max_overs}): ", min_val=1, max_val=max_overs)
    t1_played_overs = get_float_input(f"Team 1 overs played (e.g., 18.5): ", min_val=0, max_val=t1_total_overs)
    t1_wickets = get_int_input("Team 1 wickets lost: ", min_val=0, max_val=10)

    # Check for zero resource usage early
    if calculator.get_resources_used(t1_total_overs, t1_played_overs, t1_wickets) <= 0:
        print("\nError: Team 1's innings resulted in 0 or negative resources used. Cannot perform D/L calculation.")
        return

    if calc_type == "1":
        # --- Calculate Target ---
        print("\n--- Team 2 Innings (Chasing) ---")
        t2_total_overs = get_float_input(f"Team 2 scheduled overs (e.g., 15): ", min_val=1, max_val=max_overs)
        
        target = calculator.calculate_target(
            team1_score=t1_score,
            team1_total_overs=t1_total_overs,
            team1_overs_played=t1_played_overs,
            team1_wickets_lost=t1_wickets,
            team2_total_overs=t2_total_overs
        )
        if target > 0:
            print("\n--- D/L RESULT ---")
            print(f"Team 2 Target: {target} runs in {t2_total_overs} overs.")

    elif calc_type == "2":
        # --- Calculate Par Score ---
        # First, get Team 1's resources used
        t1_resources_used = calculator.get_resources_used(t1_total_overs, t1_played_overs, t1_wickets)
            
        print("\n--- Team 2 Innings (Interruption) ---")
        t2_total_overs = get_int_input(f"Team 2 originally scheduled overs (e.g., {max_overs}): ", min_val=1, max_val=max_overs)
        t2_played_overs = get_float_input(f"Team 2 overs played at interruption (e.g., 15.2): ", min_val=0, max_val=t2_total_overs)
        t2_wickets = get_int_input("Team 2 wickets lost at interruption: ", min_val=0, max_val=10)
        t2_score = get_int_input("Team 2 score at interruption: ", min_val=0)

        if t2_played_overs == 0:
            print("\nError: Cannot calculate a par score before Team 2 has played any overs.")
            print("If the innings is reduced before it starts, please use Calculation Type 1 (Target).")
            return

        par_score = calculator.calculate_par_score(
            team1_score=t1_score,
            team1_resources_used=t1_resources_used,
            team2_total_overs=t2_total_overs,
            team2_overs_played=t2_played_overs,
            team2_wickets_lost=t2_wickets
        )
        
        print("\n--- D/L RESULT ---")
        print(f"At {t2_played_overs} overs, the Par Score for Team 2 is: {par_score} runs.")
        if t2_score > par_score:
            print(f"Team 2's score ({t2_score}) is ABOVE par. They are AHEAD.")
        elif t2_score == par_score:
            print(f"Team 2's score ({t2_score}) is EQUAL to par. The match is TIED.")
        else:
            print(f"Team 2's score ({t2_score}) is BELOW par. They are BEHIND.")

    elif calc_type == "3":
        # --- Calculate Revised Target ---
        # First, get Team 1's resources used
        t1_resources_used = calculator.get_resources_used(t1_total_overs, t1_played_overs, t1_wickets)
            
        print("\n--- Team 2 Innings (Interruption & Resumption) ---")
        t2_total_overs_orig = get_int_input(f"Team 2 *originally* scheduled overs (e.g., {max_overs}): ", min_val=1, max_val=max_overs)
        t2_played_overs = get_float_input(f"Team 2 overs played at interruption (e.g., 15.2): ", min_val=0, max_val=t2_total_overs_orig)
        t2_wickets = get_int_input("Team 2 wickets lost at interruption: ", min_val=0, max_val=10)
        t2_score = get_int_input("Team 2 score at interruption: ", min_val=0)
        t2_total_overs_new = get_float_input(f"Team 2's *new* total overs (e.g., 15): ", min_val=t2_played_overs, max_val=t2_total_overs_orig)

        new_target, runs_to_get, overs_remaining = calculator.calculate_revised_target(
            team1_score=t1_score,
            team1_resources_used=t1_resources_used,
            team2_total_overs_orig=t2_total_overs_orig,
            team2_overs_at_stop=t2_played_overs,
            team2_wickets_at_stop=t2_wickets,
            team2_score_at_stop=t2_score,
            team2_total_overs_new=t2_total_overs_new
        )
        
        print("\n--- D/L REVISED TARGET ---")
        print(f"Team 2's new final target is {new_target} runs.")
        print(f"They must score {runs_to_get} more runs in the remaining {overs_remaining:.1f} overs.")


if __name__ == "__main__":
    main()