from ortools.sat.python import cp_model
import pandas as pd


class residentsPartialSolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, shifts, num_residents, num_weeks, num_rotations, sols):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self._shifts = shifts
        self._num_residents = num_residents
        self._num_weeks = num_weeks
        self._num_rotations = num_rotations
        self._solutions = set(sols)
        self._solution_count = 0
        self.sol = []

    def on_solution_callback(self):
        sol = [ [''] * self._num_weeks for _ in range(self._num_residents)] 
        sol2 = [ [0] * self._num_weeks for _ in range(self._num_rotations)] 
        if self._solution_count in self._solutions:
            print('Solution %i' % self._solution_count)
            for w in range(self._num_weeks):
                for r in range(self._num_residents):
                    for s in range(self._num_rotations):
                        if self.Value(self._shifts[r, s, w]):
                            sol[r][w] = s
            p = pd.DataFrame(sol)
            print(p)
            print()
            for w in range(self._num_weeks):
                for s in range(self._num_rotations):
                    for r in range(self._num_residents):
                        if self.Value(self._shifts[r, s, w]):
                            sol2[s][w] += 1
            p = pd.DataFrame(sol2)
            print(p)
            print()
        self._solution_count += 1

    def solution_count(self):
        return self._solution_count
