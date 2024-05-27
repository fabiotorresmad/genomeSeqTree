"""Main script of buildGenTree project"""

import os
import io
import sys
import logging
import argparse
import traceback
import json
import requests
import zipfile
import time
import gc
import pandas as pd
import subprocess
import pkg_resources

from buildGenTree.libs.logger import setup_logger
from buildGenTree.libs.parser import get_parser
from buildGenTree.libs.bash import exec


LOG = logging.getLogger(__name__)
os.makedirs(os.getcwd() + '/logs', exist_ok=True)

CURR_DIR = os.getcwd()
PIP_PACKETS_FILE = CURR_DIR + '/requirements.txt'
FASTA_DIR = CURR_DIR + '/buildGenTree/fastaSrc'
MLST_DIR = CURR_DIR + '/buildGenTree/mlst/bin'
MLST_JSON_FILE = CURR_DIR + '/buildGenTree/fastaSrc/tmpST.json'
SRC_DB_FILE = None
OUT_TSV_FILE = None

def read_requirements() -> list[str]:
    with open(PIP_PACKETS_FILE, 'r') as file:
        requirements = file.readlines()
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith('#')]
    return requirements

def check_pip_packets() -> bool:
    required_packages = read_requirements()
    
    # Get packet list
    installed_packages = {pkg.key for pkg in pkg_resources.working_set}
    
    # Check if packets are installed
    missing_packages = [pkg for pkg in required_packages if pkg.split('==')[0] not in installed_packages]
    return missing_packages == []

def install_missing_packets():
    LOG.info("- Installing missing Python packets.")
    subprocess.check_call([f'python3', '-m', 'pip', 'install', '-r', 'requirements.txt'])

def get_submodule_paths() -> list:
    submodule_paths = []
    if os.path.exists('.gitmodules'):
        with open('.gitmodules') as f:
            lines = f.readlines()
            for line in lines:
                if 'path' in line:
                    path = line.split('=')[1].strip()
                    submodule_paths.append(path)
    return submodule_paths

def is_git_repository(path: str) -> bool:
    try:
        subprocess.check_output(['git', '-C', path, 'rev-parse', '--is-inside-work-tree'],
                                stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

def check_submodules() -> bool:
    submodule_paths = get_submodule_paths()
    all_cloned = True
    for path in submodule_paths:
        if not os.path.isdir(path) or not is_git_repository(path):
            all_cloned = False
            LOG.warning(f"- Submodule {path} is not cloned properly.")
    return all_cloned

def install_missing_submodules():
    LOG.info("- Installing missing submodules.")
    subprocess.check_call(['git', 'submodule', 'update', '--init', '--recursive'])

def setup_enviroment() -> None:
    global SRC_DB_FILE, OUT_TSV_FILE
    CURR_DIR = os.getcwd()
    os.makedirs(FASTA_DIR, exist_ok=True)
    LOG.info("- Created fastaSrc folder.")

    if not os.path.exists(f"{MLST_DIR}/mlst"):
        raise FileNotFoundError("mlst file not found.")
    
    exec([f"chmod +x {MLST_DIR}/mlst"])
    LOG.info("- mlst file set executable.")

    tvs_file = ARGS.file_src
    if not 'tsv' in tvs_file.split('.')[-1]:
        raise TypeError("The source file must have a tsv extension.")

    if not os.path.exists(f"{tvs_file}"):
        raise FileNotFoundError(f"The source file not found")
    else:
        SRC_DB_FILE = tvs_file
        LOG.info("- Source file was found.")
    
    if ARGS.out_file and ARGS.out_file[-4:] == '.tsv':
        OUT_TSV_FILE = ARGS.out_file
    else:
        OUT_TSV_FILE = 'filtered_genomes.tsv'
    LOG.warning(f'- Output file will save on {OUT_TSV_FILE}\n')

def get_credentials() -> dict:
    cur_dict: dict = {}
    try:
        file = open(CURR_DIR + '/buildGenTree/src/credentials.json')
    except FileNotFoundError as e:
        LOG.error(f"File not found - {e}")
        return {}

    cur_dict = json.load(file)
    if "" in cur_dict.values():
        raise ValueError("Empty values on credentials JSON!")
    
    cur_dict['genome'] = ' '.join(ARGS.group)
    cur_dict['st_filter'] = ARGS.st
    
    return cur_dict

def preprocess_data(organism_grp: str) -> pd.DataFrame:
    LOG.debug(f"Load dataframe for {SRC_DB_FILE} file")
    data_df = pd.read_table(SRC_DB_FILE, delimiter='\t', low_memory=False)
    LOG.debug(data_df)
    filter_data_df = data_df.loc[
        data_df['Assembly'].str.upper().str.startswith('GCA_', na=False) &
        data_df['#Organism group'].str.lower().str.startswith(organism_grp.lower(), na=False)
    ]
    data_sort_df = filter_data_df.sort_values(by='Assembly')
    # Reiniciar el índice
    data_sort_df.reset_index(drop=True, inplace=True)
    return data_sort_df

def download_fna(assembly_accession, ncbi_access, output_file) -> None:
    url = ( f"{ncbi_access['api_uri']}/{assembly_accession}"
            f"/download?include_annotation_type=GENOME_FASTA")
    if ncbi_access['api_key']:
        response = requests.get(
            url=url,
            headers={'api-key': ncbi_access['api_key']},
            stream=True)
    else:
        response = requests.get(url=url,stream=True)
    response.raise_for_status()     # Verificar que la solicitud fue exitosa

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        fna_file = next((s for s in zip_ref.namelist() if s.endswith('.fna')), None)
        if fna_file:
            # Extraer el archivo .fna y guardarlo en el archivo de salida
            with zip_ref.open(fna_file) as fna, open(output_file, 'wb') as out_f:
                out_f.write(fna.read())
            LOG.debug(f"File downloaded and saved to {output_file}")
        else:
            raise Exception("File with extension fna not found!")

def run_mlst(fasta_file: str) -> bool:
    try:
        exec([f"{MLST_DIR}/mlst {fasta_file} --json {MLST_JSON_FILE} --quiet"])
    except Exception as e:
        raise ChildProcessError(e)

def check_mlst(st_val: int) -> int:
    try:
        mlst_data = open(MLST_JSON_FILE)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found - {e}")
    else:
        mlst_json = json.load(mlst_data)
        mlst_data.close()
        mlst_val = mlst_json[0]['sequence_type']

        if '-' in mlst_val:
            return -1
        return int(mlst_val) == st_val

def filter_data_by_st() -> None:
    LOG.info("1. Setup enviroment")
    setup_enviroment()

    credentials_dict: dict = {}
    assemblyIds: list = []

    credentials_dict = get_credentials()
    st_value: int = credentials_dict["st_filter"]
    
    LOG.info("2. Pre process file source")
    gca_df: pd.DataFrame = preprocess_data(credentials_dict["genome"])
    tsv_out_df = pd.DataFrame(columns=gca_df.columns)
    LOG.info(f"- Was found {len(gca_df)} assembly accessions.\n")

    LOG.info("3. Filter genomes by sequence type")
    for idx, assembly in enumerate(gca_df['Assembly']):
        fasta_file = f'{FASTA_DIR}/{assembly}.fna'

        try:
            if not os.path.exists(fasta_file):
                download_fna(
                    assembly_accession=assembly,
                    ncbi_access=credentials_dict,
                    output_file=fasta_file
                )
            run_mlst(fasta_file)
            if check_mlst(st_value):
                if len(tsv_out_df) == 0 or assembly != tsv_out_df.iloc[-1]['Assembly']:
                    LOG.debug(f"- {assembly}: The sequence type is equal from that required.")
                    tsv_out_df = pd.concat([tsv_out_df, gca_df.loc[[idx]]], ignore_index=True)
                else:
                    LOG.warning(f"- {assembly}: Duplicated in output file.")
            else:
                if os.path.exists(fasta_file):
                    os.remove(fasta_file)
                LOG.warning(f"- {assembly}: fna file was deleted.")
        except Exception as e:
            LOG.error(f'{e}')
            pass
    
    # Save csv_df on TSV file
    tsv_out_df.to_csv(OUT_TSV_FILE, sep='\t', index=False)
    LOG.info(f"Filtered data saved to {OUT_TSV_FILE}")

def main():
    # check platform
    if sys.platform == 'win32':
        LOG.error("This program is not yet available on Windows OS.")
        sys.exit(0)
    
    # Check prerequisites
    LOG.info("Check prerequisites.")
    if not check_submodules():
        install_missing_submodules()
    LOG.info("- All submodules are cloned properly.")

    if not check_pip_packets():
        install_missing_packets()
    LOG.info("- All packets was installed!\n")

    filter_data_by_st()


if __name__ == "__main__":
    parser = get_parser()
    ARGS = parser.parse_args()
    setup_logger("build_gen_tree", ARGS.log_level, ARGS.stream_output)

    try:
        main()
    except Exception as e:
        LOG.error("A fatal exception occurred: %s", e)
        LOG.error("Traceback: %s", traceback.format_exc())
    else:
        LOG.info("-- Program finished --")
        sys.exit(0)
    finally:
        sys.exit(2)