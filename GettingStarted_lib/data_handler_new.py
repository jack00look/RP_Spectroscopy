from pathlib import Path #easier filesystem path
import logging #to create the log files with our messages in addition to the stand python ones
from GettingStarted_lib.general_lib import setup_logging

import numpy as np
import yaml #data serialization for configuration files
import traceback

class DataHandler:

    REFERENCE_LINES_FOLDER = Path(__file__).parent / "reference_lines" #creates the folder in which the reference lines should be put
    LOG_FILE = Path(__file__).parent / "data_handler.log" #creates the log file

    def __init__(self, board): #each time a class object is created it automatically initialize these object attributes
        self.board = board
        self.reference
        self.logger = logging.getLogger(self.__class__.__name__) #creates a logger linked to the new class element
        setup_logging(self.logger, self.LOG_FILE)
        self._load_reference_lines()

    def _load_reference_lines(self):
        """
        Load all reference lines from the REFERENCE_LINES_FOLDER directory into a dictionary formatted as {"x", "y", "V_lock_start", "V_lock_end"}. For each line there must be:
            - a "REFERENCE_LINE_*.npy" file formatted in 2 columns containing x and y coordinates of the line plot;
            - a "REFERENCE_LINE_*.yaml" file formatted as XXXX containing the starting and ending scan region voltage for the associated line.
        """
        self.reference_lines = {} #creates the dictionary
        try: #tries to upload in the dictionary the reference lines
            for path in self.REFERENCE_LINES_FOLDER.glob("REFERENCE_LINE_*.npy"): #for every path in the folder which name matches
                key = path.stem.replace("REFERENCE_", "") # ../REFERENCE_LINE_*.npy --> LINE_*
                reference_line = np.loadtxt(path, delimiter='\t', comments="#", dtype=np.float64) #uploads the nparray from the file
                locking_region_path = path.with_suffix('.yaml')
                with open(locking_region_path, 'r') as f:
                    locking_region = yaml.safe_load(f)
                reference_line_dict = {
                    "x": reference_line[:, 0],
                    "y": reference_line[:, 1],
                    "V_lock_start": locking_region.get("V_lock_start"),
                    "V_lock_end": locking_region.get("V_lock_end"),
                }
                self.reference_lines[key] = reference_line_dict
                self.logger.debug(f"Loaded reference line: {path.name}") #writes a debug message
            self.logger.info("All reference lines loaded successfully.") #writes a debug message
        except FileNotFoundError as e: #if there are no files
            self.logger.error(f"Reference line file not found: {e}")
            self.logger.error(traceback.format_exc())
        except Exception as e: #if another error occures
            self.logger.error(f"Failed to load reference lines: {e}")
            self.logger.error(traceback.format_exc())

    def save_reference_line(self, key, signal,V_lock_start, V_lock_end):
        """
        Save a reference line to the REFERENCE_LINES_FOLDER directory. If a reference with the same key already exists it overwrites it.
            - self.reference_lines contains all the already uploaded reference lines;
            - key must be a string "LINE_*";
            - signal must be a dictionary {"x", "y"};
            - V_lock_start and V_lock_end are expressed in volts.
        """
        if key in self.reference_lines:
            self.logger.warning(f"Reference line with key {key} already exists. Overwriting.")
        
        reference_line = np.column_stack((signal['x'], signal['y'])) #cretes the np array with the signal
        file_path = self.REFERENCE_LINES_FOLDER / f"REFERENCE_LINE_{key}.npy"
        np.savetxt(file_path, reference_line, delimiter='\t', header='#x\ty', comments='') #saves the reference_line signal
        locking_region = {
            "V_lock_start": V_lock_start,
            "V_lock_end": V_lock_end
        } #defines the locking_region dictionary
        file_path_yaml = file_path.with_suffix('.yaml')
        with open(file_path_yaml,'w') as f:
            yaml.dump(locking_region,f) #saves the locking region infos in the .yaml file
        self.reference_lines[key] = {
            "x": signal['x'],
            "y": signal['y'],
            "V_lock_start": V_lock_start,
            "V_lock_end": V_lock_end
            } #creates the dictionary element
        self.logger.info(f"Saved reference line: {file_path.name}")

    def reset_reference_lines(self):
        """
        Reset the reference lines dictionary and remove all files in the REFERENCE_LINEA_FOLDER. 
        """
        self.reference_lines.clear()
        for path in self.REFERENCE_LINES_FOLDER.glob("REFERENCE_LINE_*"):
            try:
                path.unlink() #delates the file 
                self.logger.debug(f"Deleted reference line file: {path.name}")
            except Exception as e:
                self.logger.error(f"Failed to delete reference line file {path.name}: {e}")
        self.logger.info("All reference lines reset successfully.")
