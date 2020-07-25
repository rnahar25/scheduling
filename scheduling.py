#Python CP_Model
#https://google.github.io/or-tools/python/ortools/sat/python/cp_model.html

#Google_OR for CP-SAT solver
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from ortools.sat.python import cp_model
import pandas as pd

from constraints import negated_bounded_span
from constraints import add_soft_sequence_constraint
from constraints import add_soft_sum_constraint
from constraints import add_only_2_or_4_sequence_constraint
from constraints import add_hard_sequence_len_constraint

import sys
seconds = 5
if len(sys.argv) > 1:
    seconds = int(sys.argv[1])



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



def apply_service_rules(model, conseq_wks, num_weeks_total, num_res_per_wk, services, all_residents, shift):
    print(conseq_wks, num_res_per_wk, services) 
    for r in all_residents:
        for s in services:
            works = [shift[r,s,w] for w in range(num_weeks_total)]
            if conseq_wks == 24:
                service_hard_max = 4
                add_only_2_or_4_sequence_constraint(model, works, service_hard_max)
            else:
                add_hard_sequence_len_constraint(model, works, conseq_wks)

    # Applying constraint for number of residents on the service
    for s in services: 
        if num_res_per_wk == 40:
            for w in range(num_weeks_total//2):
                model.Add(sum(shift[r,s,w] for r in all_residents) >= 4)
        else:
            for w in range(num_weeks_total):
                model.Add(sum(shift[r,s,w] for r in all_residents) >= num_res_per_wk)


def main():
    # Create the Google CP-SAT solver
    m = cp_model.CpModel()

    #Objective function penalties
    obj_int_vars = []
    obj_int_coeffs = []
    obj_bool_vars = []
    obj_bool_coeffs = []

    #Create Data
    num_residents = 40
    num_rotations = 16 
    num_weeks = 12
    num_electives = 6

    # first number is time (weeks) second number is residents/week
    # e.g. num_24_4 means service needs either 2 or 4 weeks and 4 residents 
    num_2_4 = 1   # nmar
    num_2_40 = 1  # NF
    num_24_4 = 2  # MICU or CCU
    num_4_2 = 2
    num_4_1 = num_rotations - (num_electives + 1+1+2+2) # 21

    all_residents = range(num_residents)
    all_rotations = range(num_rotations)
    all_weeks = range(num_weeks)
    all_electives = range(num_electives)
    all_hard_services = range(num_electives, num_rotations)
    min_rotations_per_resident = 1 #(num_rotations - 5)


    #Define decision variables
    shift = {}
    for r in range(num_residents):
        for s in range(num_rotations):
            for w in range(num_weeks):
                shift[r,s,w] = m.NewBoolVar('shift_%i_%i_%i' % (r, s, w))


    service_wk_len_constraints = [
        (2, 2, 0, 2, 2, 0)  # elective
    ]

    # Forcing residents to be on elective two weeks in a row
    hard_min, soft_min, min_cost, soft_max, hard_max, max_cost = service_wk_len_constraints[0]
    for r in all_residents:
        for e in all_electives:
            works = [shift[r,e,w] for w in range(num_weeks)]
            variables, coeffs = add_soft_sequence_constraint(m, works, hard_min, soft_min, min_cost, soft_max, hard_max,
                max_cost, 'shift_constraint(resident %i, service %i)' % (r, e))

    # # Forcing residents to be on hard service two or four weeks in a row
    # service_hard_max = 4
    # for r in all_residents:
    #     for h in all_hard_services:
    #         works = [shift[r,h,w] for w in range(num_weeks)]
    #         add_only_2_or_4_sequence_constraint(m, works, service_hard_max)


    #Intermittant Variable - Resident on service per week
    on_rotation = {}
    for r in all_residents:
        for w in all_weeks:
            on_rotation[r,w] = m.NewBoolVar('on_rotation_%i_%i' % (r, w))

    for r in all_residents:
        for w in all_weeks:
            m.Add((on_rotation[r,w] == sum([shift[r,s,w] for s in all_rotations])))


        
    # #Each HARD service has 2 resident per week
    # for w in all_weeks:
    #     for s in all_hard_services: 
    #         m.Add(sum(shift[r,s,w] for r in all_residents) >= 2)

    #A resident cannot be on more than one service in a given week
    for r in all_residents:
        for w in all_weeks:
            m.Add(sum(shift[r,s,w] for s in all_rotations) <= 1)

    #A resident does a given service for two weeks
    for s in all_hard_services:
        for r in all_residents:
            m.Add(sum(shift[r,s,w] for w in all_weeks) <= 4)

    #A resident does a given ELECTIVE for TWO weeks
    for e in all_electives:
        for r in all_residents:
            m.Add(sum(shift[r,e,w] for w in all_weeks) <= 2)


    service_breakdown = [num_2_4, num_2_40, num_24_4, num_4_2, num_4_1]
    wk_rules = [2, 2, 24, 4, 4]
    res_rules = [4, 40, 4, 2, 1]

    for i in range(len(service_breakdown)):
        serv_ind_start = num_electives + sum(service_breakdown[:i])
        serv_list = range(serv_ind_start, serv_ind_start + service_breakdown[i])
        apply_service_rules(m, wk_rules[i], num_weeks, res_rules[i], serv_list, all_residents, shift)


    # Constraints on rests per year.
    weekly_sum_constraints = (10, 11, 10, 11, 12, 10)
    

    # Forcing residents to have 1 to 2 weeks of vacation  
    hard_min, soft_min, min_cost, soft_max, hard_max, max_cost = weekly_sum_constraints
    for r in all_residents:
        works = [shift[r,s,w] for w in range(num_weeks) for s in range(num_rotations)]
        variables, coeffs = add_soft_sum_constraint(m, works, hard_min, soft_min, min_cost, soft_max, hard_max,
            max_cost, 'shift_constraint(resident %i, service %i)' % (r, s))

    # for r in all_residents:
    #         num_rotations_worked = sum(shift[r,s,w] for w in all_weeks for s in all_rotations)
    #         m.Add(min_rotations_per_resident <= num_rotations_worked)

    #Objective Function
    # m.Minimize(sum(obj_bool_vars[i] * obj_bool_coeffs[i] for i in range(len(obj_bool_vars)))
    #    + sum(obj_int_vars[i] * obj_int_coeffs[i] for i in range(len(obj_int_vars))))            # -- uncomment this line to get one solution with object minimize fn



    solver = cp_model.CpSolver()
    solver.parameters.linearization_level = 0
    # Display the first five solutions.
    a_few_solutions = range(2)
    solution_printer = residentsPartialSolutionPrinter(shift, num_residents,
                                                    num_weeks, num_rotations,
                                                    a_few_solutions)
    solver.SearchForAllSolutions(m, solution_printer)
    # solver.SolveWithSolutionCallback(m, solution_printer)   # -- uncomment this line to get one solution with object minimize fn

    #Call the solver and display the results        
    # solver = cp_model.CpSolver()
    # solver.parameters.linearization_level = 0
    # # Sets a time limit of 10 seconds.
    # solver.parameters.max_time_in_seconds = 300
    # status = solver.Solve(m)
    # print('Status = %s' % solver.StatusName(status))


if __name__ == '__main__':
    main()
