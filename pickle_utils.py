# pickle_utils.py
import pickle
import os

def save_pickle(data, filepath):
    """Saves data to a file using pickle."""
    try:
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        print(f"Successfully saved data to {filepath}")
    except Exception as e:
        print(f"Error saving data to {filepath}: {e}")

def load_pickle(filepath):
    """Loads data from a pickle file."""
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        return None
    try:
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        print(f"Successfully loaded data from {filepath}")
        return data
    except Exception as e:
        print(f"Error loading data from {filepath}: {e}")
        return None 