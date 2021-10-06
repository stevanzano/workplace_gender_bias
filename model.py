%load_ext autoreload
%autoreload 2

from util import *
from entities import *
import yaml
from multiprocessing import Pool
from functools import partial
from random import seed
import sys
import os
from collections import Counter, defaultdict
from IPython.core.debugger import set_trace
import yaml
import numpy as np


def model_runner(chunk_data,default_params_dict,n_replications, output_folder):
    effect_size = np.array([0,0.00249377,0.00990099,0.02200489,0.03846154,0.05882353]) * 2
    chunk_num, chunk = chunk_data
#     turn_output_file = open(os.path.join(output_folder,"turn_output_{i}.tsv".format(i=chunk_num)),"w")
    for i,row in enumerate(chunk):
        if i % 1000 == 0:
            print chunk_num, i
        # figure 1,2
        stretch_bar = row['stretch_project_biased_bar']
        complain = row['project_women_percent_complain_on_mixed_success']
        reward_mean = row['project_reward_mean']
        start,end = row['promotion_intervention_span']
        w = row['promotion_intervention_norm']
#         l = [macro_norm,stretch_bar,complain,reward_mean]
#         if l[0] == 0.02 and l[1] == 1.01 and l[2] == 0.01: pass
#         elif l[0] == 0.04 and l[1] == 1.02 and l[2] == 0.02: pass
#         elif l[0] == 0.06 and l[1] == 1.03 and l[2] == 0.03: pass
#         elif l[0] == 0.08 and l[1] == 1.04 and l[2] == 0.04: pass
#         elif l[0] == 0.1 and l[1] == 1.05 and l[2] == 0.05: pass
#         else: continue
        # figure1,2
        b1 = row['idv_succ_effect_size']
        b2 = row['idv_fail_effect_size']
        b3 = row['mixed_succ_effect_size']
        b4 = row['mixed_fail_effect_size']
        l = [b1,b2,b3,b4,complain,stretch_bar,reward_mean,start,end,w]
#         if l[0] == l[1] == l[2] == l[3] == l[4]  == 0.01 and l[5] == 1.01: pass
#         elif l[0] == l[1] == l[2] == l[3] == l[4]  == 0.03 and l[5] == 1.03: pass
#         else: continue
        
        # figure 3
#         start,end = row['promotion_intervention_span']
#         norm = row['promotion_intervention_norm']
#         reward_mean = row['project_reward_mean']
#         l = [start,end,norm,reward_mean]


        name = '_'.join([str(n) for n in l])
#         turn_output_file = open(os.path.join(output_folder,"turn_output_{i}.tsv".format(i=chunk_num)),"w")
        turn_output_file = open(os.path.join(output_folder,name + '.tsv'),"w")
        turn_output_agent_file = open(os.path.join(output_folder,name + '_agent.tsv'),"w")
        turn_output_promotion_file = open(os.path.join(output_folder,name + '_promotion.tsv'),"w")
        for replication in range(n_replications):
            print "\t", replication
            #print replication
            params_dict = default_params_dict.copy()
            params_dict.update(row)
            params_dict['replication_number'] = replication
            params_dict['run_number'] = int(params_dict['run_number'])
            params_dict['turn_output_file'] = turn_output_file
            params_dict['turn_output_agent_file'] = turn_output_agent_file
            params_dict['turn_output_promotion_file'] = turn_output_promotion_file
            run_single_model(params_dict)
        turn_output_file.close()
        turn_output_agent_file.close()
        turn_output_promotion_file.close()





def run_single_model(params_dict):
    #params_dict['agent_output_file'] = agent_output_file
    P = ParameterHolder(params_dict)
    # How is agent competence/likeability determined?
    agent_promotability_fn = promotability_function_factory(P)
    # Functions for new agents
    initial_level_sex_fn = sex_function_factory(P, len(P.hierarchy_sizes)-1, 0)
    # How agents are promoted
    promotion_function = promotion_function_factory(P)
    # How agents decide to leave
    leave_function = leave_function_factory(P)
    assign_projects_fn = assign_projects_factory(P)
    agent_id = 0
    # Initialize the company
    company_hierarchy = []
    for level, level_size in enumerate(P.hierarchy_sizes):
        sex_fn = sex_function_factory(P, level, 0)
        l = []
        for _ in range(level_size):
            l.append(Agent(sex_function = sex_fn,
                            promotability_function=agent_promotability_fn,
                            time_of_creation=0,
                           id=agent_id))
            agent_id +=1
        company_hierarchy.append(l)

    # Okay, start the simulation

    # For each project cycle
    for turn in range(P.n_project_cycles):
        #### Print stats about the company
        print_stats(P, turn, company_hierarchy)

        # For each hierarchy level
        bias_each_level = []
        for level_index, company_level in enumerate(company_hierarchy):

            # compute the percentage of women at the level
            # for bias adjustments
            if P.project_bias_type == 'effect_size':
                if level_index == 0:
                    perc_male = (sum([agent.is_male for agent in company_level]) /
                                  float(len(company_level)))
                else:
                    lookup = company_hierarchy[level_index-1]
                    perc_male = (sum([agent.is_male for agent in lookup]) /
                                  float(len(lookup)))

                proj_success_fn,succ_bias = bias_function_factory(P,perc_male, 'success',turn)
                proj_failure_fn,fail_bias = bias_function_factory(P,perc_male, 'fail',turn)
                bias_each_level.append(succ_bias)
                
            else:
                if P.project_bias_type =='threshold':
                    perc_women = (sum([not agent.is_male for agent in company_level]) /
                                  float(len(company_level)))
                elif P.project_bias_type == 'micro_macro':
                    if level_index == 0:
                        perc_women = 0.5
                    else:
                        lookup = company_hierarchy[level_index-1]
                        perc_women = (sum([not agent.is_male for agent in lookup]) /
                                  float(len(lookup)))
                # What happens on project success and failure?
                proj_success_fn = project_function_factory(P,perc_women, 'success')
                proj_failure_fn = project_function_factory(P,perc_women, 'fail')

            #### Assign Projects
            projects = assign_projects_fn(P, company_level, turn, level_index)
            #### Carry out the projects
            for project in projects:
                # Is the project successful? 1 for yes, 0 for no
                if project.is_successful:
                    for agent in project.agents:
                        agent.num_successful_projects += 1
                    proj_success_fn(project)
                else:
                    for agent in project.agents:
                        agent.num_failed_projects += 1
                    proj_failure_fn(project)
        # If its a promotion period
        if turn % P.projects_per_promotion_cycle == 0:

            ### Compute the turnover at the company
            men_leave,women_leave = [],[]
            for level_iter, company_level in enumerate(company_hierarchy):
                # See who leaves
                leaving_agents, staying_agents = leave_function(P,company_level,level)
                # Remove them
                company_hierarchy[level_iter] = staying_agents
                men_leave.append(len([agent for agent in leaving_agents if agent.is_male]))
                women_leave.append(len(leaving_agents) - men_leave[-1])
            
            men_promoted,women_promoted = [0],[0]
            ### Now, promote up, starting at the top
            for level_iter in range(len(company_hierarchy)-1):
                company_level = company_hierarchy[level_iter]
                    # find the top K at the level below me
                hire_from = company_hierarchy[level_iter + 1]
                current_level = len(company_hierarchy) - level_iter
                if P.promotion_intervention and turn >= P.promotion_intervention_span[0] and turn<=P.promotion_intervention_span[1]:
                    women_lowerbar = P.hierarchy_sizes[level_iter] * P.promotion_intervention_bar
                    women_lowerbar = int(ceil(women_lowerbar))
                    women_current = sum([ not i.is_male for i in company_level])
                    agents_to_hire,agents_remaining = promotion_function(hire_from,
                                                                          P.hierarchy_sizes[level_iter]-len(company_level),\
                                                                         n_women=women_lowerbar-women_current)
                else:
                     agents_to_hire,agents_remaining = promotion_function(hire_from,
                                                                          P.hierarchy_sizes[level_iter]-len(company_level))
                men_promoted.append(len([agent for agent in agents_to_hire if agent.is_male]))
                women_promoted.append(len([agent for agent in agents_to_hire if not agent.is_male]))
                
                # promote them
                company_hierarchy[level_iter] = company_level + agents_to_hire
                # leave the remaining agents
                company_hierarchy[level_iter + 1] = agents_remaining     
            ### Add new agents to the bottom
            new_agents = []
            initial_level_sex_fn = sex_function_factory(P, len(P.hierarchy_sizes)-1, turn)

            for _ in range(P.hierarchy_sizes[-1] - len(company_hierarchy[-1])):
                new_agents.append(Agent(sex_function = initial_level_sex_fn,
                                        promotability_function=agent_promotability_fn,
                                        time_of_creation=turn,
                                        id = agent_id))
                agent_id +=1
            company_hierarchy[-1] = company_hierarchy[-1] + new_agents
            print_stats_promotion(P, turn, company_hierarchy,men_leave,women_leave,men_promoted,women_promoted, bias_each_level)

    
sys.argv = ['','minimal_nodownward.yaml',
            'default_params.yaml',
            'new_output',
            '100',
            '6',
            '14260']



if __name__ == "__main__":

    if len(sys.argv) != 6:
        print 'Usage: python model.py [path to experiment file] ',
        print '[path to default params file] [path to desired output folder] ',
        print ' [n_replications_per_condition] [n_cores] [random seed]'


    experiment_file, default_params_file, output_folder, n_replications, n_cores, rseed = sys.argv[1:]
    default_params_dict = yaml.load(open(default_params_file))
    n_replications = int(n_replications)
    n_cores = int(n_cores)
    experiment_details = yaml.load(open(experiment_file))
    
    print experiment_details
    experimental_runs = expand_grid(experiment_details)
    experimental_runs = experimental_runs.reset_index().rename(index=str,columns={"index":"run_number"})

    try:
        os.mkdir(output_folder)
    except:
        print "Not going to overwrite output!"
        #sys.exit(-1)
    ## use yaml files
    experimental_runs.to_csv(os.path.join(output_folder, "experiment_details.csv"),index=False)
    experimental_runs = [x[1].to_dict() for x in experimental_runs.iterrows()]
    
    print(int(len(experimental_runs) / n_cores))
    chunked = list(enumerate(chunkify(experimental_runs, n_cores)))
    default_params_dict = yaml.load(open(default_params_file))
    runner_partial = partial(model_runner,
                             default_params_dict=default_params_dict,
                             n_replications=n_replications,
                             output_folder=output_folder)
    if n_cores > 1:
        p = Pool(n_cores)
        res = p.map(runner_partial, chunked)
        p.close()
        p.terminate()
    else:
        # run on single process
        for c in chunked:
            runner_partial(c)

