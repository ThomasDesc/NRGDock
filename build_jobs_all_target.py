import sys
import os
from main import get_params_dict
from main import get_device

def find_file(end, path):
    filenames = next(os.walk(path), (None, None, []))[2]
    for filename in filenames:
        if filename.endswith(end):
            return filename


def count_molecules(path):
    line_list = []
    ligand_counter = 0
    name_list = []
    same_name_counter = 0

    with open(path) as f:
        lines = f.readlines()
        for t, line in enumerate(lines):
            if line.find("@<TRIPOS>MOLECULE") != -1:
                ligand_counter += 1
                line_list.append(t)
                name = lines[t+1].strip()
                if len(name_list) != 0:
                    previous_name = name_list[-1].split("_")[0]
                    if previous_name != name:
                        name_list.append(name)
                        same_name_counter = 0
                    else:
                        same_name_counter += 1
                        name += "_" + str(same_name_counter)
                        name_list.append(name)
                elif len(name_list) == 0:
                    name_list.append(name)
    return ligand_counter, line_list, name_list


def divisible(ligand_counter, line_list, job_limit, name_list):
    number = 0
    divider = None
    final_name_list = []
    final_list = []

    for a in range(2, ligand_counter):
        if ligand_counter / a < job_limit:
            divider = a
            break
    while number < ligand_counter:
        final_list.append(line_list[number:number + divider + 1])
        final_name_list.append(name_list[number:number + divider])
        number += divider
    return final_list, final_name_list


def build_string_list(final_list, ligand_path, name_list, ga):
    command_string_list = []
    global next_job_counter
    for a, lig_group in enumerate(final_list):
        string = f"python3 {software_path}FastAID_Py/main_GA.py {ligand_path} {receptor} {binding_site} "
        if ga == 'False':
            string = string.replace("main_GA.py", "main.py")
        for c, ligand in enumerate(lig_group[:-1]):
            if c != len(lig_group) - 2:
                string += str(ligand) + ","
            else:
                string += str(ligand)
        string += " " + str(lig_group[-1])  # add line where last ligand .mol ends
        #adding names
        string += " "
        for d, name in enumerate(name_list[a]):
            if d != len(name_list[a]) - 1:
                string += str(name) + ","
            else:
                string += str(name)
        string += "\nsbatch job_" + str(next_job_counter) + ".sh"
        next_job_counter += 1
        command_string_list.append(string)
    return command_string_list


def clean_job_folder(path):
    _, _, files = next(os.walk(path + "jobs/"), (None, None, []))
    for file in files:
        os.remove(path + "jobs/" + file)


def build_sbatch_list(command_string_list):
    sbatch_list = []
    d = None
    global job_counter
    for d, command in enumerate(command_string_list):
        with open(software_path + "FastAID_Py/job_template.sh") as f:
            lines = f.readlines()
            with open(software_path + "jobs/job_" + str(job_counter + d) + ".sh", "w") as g:
                lines.append(command)
                for element in lines:
                    g.write(element)
                sbatch_list.append("sbatch job_" + str(job_counter + d) + ".sh")
    job_counter += d + 1
    return sbatch_list


def check_output_path_existence(output_path, target):
    isExist = os.path.exists(output_path + target)
    if not isExist:
        os.makedirs(output_path + target)
        final_path = output_path + target


if __name__ == "__main__":

    config_file = "/home/thomasd/projects/rrg-najmanov/thomasd/New_binding_software/FastAID_Py/config.txt"
    if not os.path.exists(config_file):
        config_file = "/home/thomasd/projects/def-najmanov/thomasd/New_binding_software/FastAID_Py/config.txt"
        if not os.path.exists(config_file):
            config_file = "config.txt"

    params_dict = get_params_dict(config_file)
    device = get_device(config_file)
    conformer = sys.argv[1]
    ga = sys.argv[2]
    software_path = None
    base_path = None

    if device == "linux":
        software_path = "/home/thomas/Desktop/New_binding_software/"
        base_path = "/home/thomas/Desktop/diverse/"
    elif device == "beluga":
        software_path = "/home/thomasd/projects/rrg-najmanov/thomasd/New_binding_software/"
        base_path = "/home/thomasd/diverse/"
    elif device == "narval":
        software_path = "/home/thomasd/projects/def-najmanov/thomasd/New_binding_software/"
        base_path = "/home/thomasd/diverse/"
    elif device == "windows":
        software_path = "C:/Users/thoma/Desktop/New_binding_software/"
        base_path = "C:/Users/thoma/Desktop/diverse/"

    #PREPARE OUTPUT FOLDER
    output_path = software_path + "results/"
    dirs = os.listdir(base_path)
    for dir in dirs:
        check_output_path_existence(output_path, dir)
    #END PREP
    clean_job_folder(software_path)
    job_counter = 0  # for naming jobs
    next_job_counter = 1000  # for instruction to start next job
    for a, dir in enumerate(dirs):
        receptor_name = dir
        print(receptor_name)
        receptor = base_path + receptor_name + "/" + find_file(".inp.pdb", base_path + receptor_name + "/")  # .inp.pdb
        binding_site = base_path + receptor_name + "/" + "getcleft/" + find_file("_sph_1.pdb",
                                                                                 base_path + receptor_name + "/" + "getcleft/")
        if conformer == "True":
            active_ligand_path = base_path + receptor_name + "/actives_final_conf.mol2"
            decoy_ligand_path = base_path + receptor_name + "/decoys_final_conf.mol2"
        else:
            if device == "linux":
                active_ligand_path = base_path + receptor_name + "/actives_final.mol2"
                decoy_ligand_path = base_path + receptor_name + "/decoys_final.mol2"
            else:
                active_ligand_path = base_path + receptor_name + "/actives_final_OG.mol2"
                decoy_ligand_path = base_path + receptor_name + "/decoys_final_OG.mol2"

        active_counter, active_line_list, active_name = count_molecules(active_ligand_path)
        decoy_counter, decoy_line_list, decoy_name = count_molecules(decoy_ligand_path)

        active_job_limit = int(1000 / ((active_counter + decoy_counter) / active_counter))
        decoy_job_limit = int(1000 / ((active_counter + decoy_counter) / decoy_counter)) - 1

        active_final_list, active_final_name_list = divisible(active_counter, active_line_list, active_job_limit, active_name)
        decoy_final_list, decoy_final_name_list = divisible(decoy_counter, decoy_line_list, decoy_job_limit, decoy_name)

        active_string_list = build_string_list(active_final_list, active_ligand_path, active_final_name_list, ga)
        decoy_string_list = build_string_list(decoy_final_list, decoy_ligand_path, decoy_final_name_list, ga)

        active_sbatch_list = build_sbatch_list(active_string_list)
        decoy_sbatch_list = build_sbatch_list(decoy_string_list)

    total_sbatch_list = []
    for i in range(0, 1000):
        string = "sbatch job_" + str(i) + ".sh"
        total_sbatch_list.append(string)
    with open(software_path + "jobs/start_jobs.sh", "w") as h:
        for element in total_sbatch_list:
            h.write(element + "\n")

