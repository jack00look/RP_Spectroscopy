import logging
import sys
import os

def setup_logging(logger, logger_file):
    """
    Sets up the logging to stream and file.
    Copied/Adapted from GettingStarted_lib/general_lib.py
    """
    # Ensure directory exists
    log_dir = os.path.dirname(logger_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            print(f"Error creating log directory {log_dir}: {e}")
            # Continue, file handler might fail but stream might work

    logger.setLevel(logging.INFO) #sets the level of this function in the logging different levels to INFO
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout) #sends logging outputs to stream in the std output
    file_handler = logging.FileHandler(logger_file) #sends logging outputs to a disk file
    
    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ) #organizes the log data as desired. It is a template
    
    console_handler.setFormatter(formatter) #chooses this formatter for the console
    file_handler.setFormatter(formatter) #chooses this formatter for the log file
    
    console_handler.setLevel(logging.INFO) #sets the level of this logging informations to INFO in the console
    file_handler.setLevel(logging.INFO) #sets the level of this logging informations to INFO in the file
    
    # Add handlers safely
    if not logger.hasHandlers(): #if the logger does not have handlers it gives them to it
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    else:
        # Clear existing handlers to avoid duplicates if called multiple times
        logger.handlers.clear()
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
