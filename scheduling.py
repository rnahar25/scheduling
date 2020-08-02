#Python CP_Model
#https://google.github.io/or-tools/python/ortools/sat/python/cp_model.html

#Google_OR for CP-SAT solver
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from ortools.sat.python import cp_model

from constraints import (negated_bounded_span, add_soft_sequence_constraint,
                        add_soft_sum_constraint, add_only_2_or_4_sequence_constraint,
                        add_hard_sequence_len_constraint)
from printer import residentsPartialSolutionPrinter

import sys

seconds = 5
if len(sys.argv) > 1:
    seconds = int(sys.argv[1])


#elective designations
CHIEF = 0
PRIMARY_CARE = 1

MIN_PRIMARY_CARE_WKS = 2 #16


def enforce_primary_care(m, res_list, all_weeks, shift):
    #All primary care residents must be on PRIMARY_CARE service for at least MIN_PRIMARY_CARE_WKS weeks
    for r in res_list:
        m.Add(sum(shift[r,PRIMARY_CARE,w] for w in all_weeks) >= MIN_PRIMARY_CARE_WKS)


def enforce_chief(m, res_list, all_weeks, shift):
    #All chief residents must be on cheif service for wks 17-27 and 49-50
    #weeks = [*range(16,27),  *range(48,50)]
    for r in res_list:
        m.Add(sum(shift[r,CHIEF,w] for w in range(8,10)) >= 2)


def apply_resident_rules(m, all_weeks, shift, num_residents):
    # splitting resident groups
    num_pcare_yr2 = 4
    num_pcare_yr3 = 2
    num_chief = 4
    num_norm_yr2 = 34
    num_norm_yr3 = num_residents - (num_pcare_yr2 + num_pcare_yr3 + num_chief + num_norm_yr2)


    resident_breakdown = [num_pcare_yr2, num_pcare_yr3, num_chief, num_norm_yr2, num_norm_yr3]
    res_type = ['pcare_yr2', 'pcare_yr3', 'chief', 'norm_yr2', 'num_norm_yr3']

    for i in range(len(resident_breakdown)):
        res_ind_start = sum(resident_breakdown[:i])
        res_list = range(res_ind_start, res_ind_start + resident_breakdown[i])
        print(res_list, res_type[i])
        if 'pcare' in res_type[i]:
            enforce_primary_care(m, res_list, all_weeks, shift)
        if 'chief' in res_type[i]:
            enforce_chief(m, res_list, all_weeks, shift)
        

class CreateSchedule():
    def __init__(self):
        # Create the Google CP-SAT solver
        self.m = cp_model.CpModel()

        #Objective function penalties
        self.obj_int_vars = []
        self.obj_int_coeffs = []
        self.obj_bool_vars = []
        self.obj_bool_coeffs = []

        #Create Data
        self.num_residents = 77 #77 #40
        self.num_rotations = 20 #73 # 16 
        self.num_weeks = 12 #50 #12
        self.num_electives = 6 #44 #6

        # first number is time (weeks) second number is residents/week
        # e.g. num_24_4 means service needs either 2 or 4 weeks and 4 residents 
        self.num_2_4 = 1   # nmar
        self.num_2_40 = 1  # NF
        self.num_24_4 = 2  # MICU or CCU
        self.num_4_2 = 2
        self.num_4_1 = self.num_rotations - (self.num_electives + 1+1+2+2) # 21


        self.all_residents = range(self.num_residents)
        self.all_rotations = range(self.num_rotations)
        self.all_weeks = range(self.num_weeks)
        self.all_electives = range(self.num_electives)
        self.all_hard_services = range(self.num_electives, self.num_rotations)
        self.min_rotations_per_resident = 1 #(num_rotations - 5)


        #Define decision variables
        self.shift = {}
        for r in range(self.num_residents):
            for s in range(self.num_rotations):
                for w in range(self.num_weeks):
                    self.shift[r,s,w] = self.m.NewBoolVar('shift_%i_%i_%i' % (r, s, w))

    def apply_service_rules(self, conseq_wks, num_weeks_total, num_res_per_wk, services, all_residents, shift):
        print(conseq_wks, num_res_per_wk, services) 
        for r in all_residents:
            for s in services:
                works = [shift[r,s,w] for w in range(num_weeks_total)]
                if conseq_wks == 24:
                    service_hard_max = 4
                    add_only_2_or_4_sequence_constraint(self.m, works, service_hard_max)
                else:
                    add_hard_sequence_len_constraint(self.m, works, conseq_wks)

        # Applying constraint for number of residents on the service
        for s in services: 
            if num_res_per_wk == 40:
                for w in range(num_weeks_total//2):
                    self.m.Add(sum(shift[r,s,w] for r in all_residents) >= 4)
            else:
                for w in range(num_weeks_total):
                    self.m.Add(sum(shift[r,s,w] for r in all_residents) >= num_res_per_wk)

    def main(self):
        apply_resident_rules(self.m, self.all_weeks, self.shift, self.num_residents)

        # Forcing residents to be on elective two weeks in a row
        for r in self.all_residents:
            for e in self.all_electives:
                works = [self.shift[r,e,w] for w in range(self.num_weeks)]
                add_hard_sequence_len_constraint(self.m, works, 2)

        #Intermittant Variable - Resident on service per week
        on_rotation = {}
        for r in self.all_residents:
            for w in self.all_weeks:
                on_rotation[r,w] = self.m.NewBoolVar('on_rotation_%i_%i' % (r, w))

        for r in self.all_residents:
            for w in self.all_weeks:
                self.m.Add((on_rotation[r,w] == sum([self.shift[r,s,w] for s in self.all_rotations])))


        #A resident cannot be on more than one service in a given week
        for r in self.all_residents:
            for w in self.all_weeks:
                self.m.Add(sum(self.shift[r,s,w] for s in self.all_rotations) <= 1)

        #A resident does a given service for two weeks
        for s in self.all_hard_services:
            for r in self.all_residents:
                self.m.Add(sum(self.shift[r,s,w] for w in self.all_weeks) <= 4)

        #A resident does a given ELECTIVE for TWO weeks
        for e in self.all_electives:
            for r in self.all_residents:
                self.m.Add(sum(self.shift[r,e,w] for w in self.all_weeks) <= 2)


        service_breakdown = [self.num_2_4, self.num_2_40, self.num_24_4, self.num_4_2, self.num_4_1]
        wk_rules = [2, 2, 24, 4, 4]
        res_rules = [4, 40, 4, 2, 1]

        for i in range(len(service_breakdown)):
            serv_ind_start = self.num_electives + sum(service_breakdown[:i])
            serv_list = range(serv_ind_start, serv_ind_start + service_breakdown[i])
            self.apply_service_rules(wk_rules[i], self.num_weeks, res_rules[i], serv_list, self.all_residents, self.shift)


        # Constraints on rests per year.
        weekly_sum_constraints = (10, 11, 10, 11, 12, 10)
        

        # Forcing residents to have 1 to 2 weeks of vacation  
        hard_min, soft_min, min_cost, soft_max, hard_max, max_cost = weekly_sum_constraints
        for r in self.all_residents:
            works = [self.shift[r,s,w] for w in range(self.num_weeks) for s in range(self.num_rotations)]
            variables, coeffs = add_soft_sum_constraint(self.m, works, hard_min, soft_min, min_cost, soft_max, hard_max,
                max_cost, 'self.shift_constraint(resident %i, service %i)' % (r, s))


        # for r in self.all_residents:
        #         self.num_rotations_worked = sum(self.shift[r,s,w] for w in self.all_weeks for s in self.all_rotations)
        #         m.Add(min_rotations_per_resident <= self.num_rotations_worked)

        #Objective Function
        # self.m.Minimize(sum(obj_bool_vars[i] * obj_bool_coeffs[i] for i in range(len(obj_bool_vars)))
        #    + sum(obj_int_vars[i] * obj_int_coeffs[i] for i in range(len(obj_int_vars))))            # -- uncomment this line to get one solution with object minimize fn



        solver = cp_model.CpSolver()
        solver.parameters.linearization_level = 0
        # Display the first five solutions.
        a_few_solutions = range(2)
        solution_printer = residentsPartialSolutionPrinter(self.shift, self.num_residents,
                                                        self.num_weeks, self.num_rotations,
                                                        a_few_solutions)
        solver.SearchForAllSolutions(self.m, solution_printer)
        # solver.SolveWithSolutionCallback(self.m, solution_printer)   # -- uncomment this line to get one solution with object minimize fn

        # Call the solver and display the results        
        solver = cp_model.CpSolver()
        solver.parameters.linearization_level = 0
        # Sets a time limit of 10 seconds.
        solver.parameters.max_time_in_seconds = 300
        status = solver.Solve(self.m)
        print('Status = %s' % solver.StatusName(status))


if __name__ == '__main__':
    c = CreateSchedule()
    c.main()
