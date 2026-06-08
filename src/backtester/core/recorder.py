import pandas as pd
from dataclasses import asdict
from typing import List, Dict
from backtester.events.types import BaseEvent

class EventSerializer:
    """
    Records every event in the backtest to a pandas DataFrame and saves it as a Parquet file
    for deterministic replay and debugging.
    """
    def __init__(self):
        self.events: List[Dict] = []

    def log_event(self, event: BaseEvent) -> None:
        # Convert dataclass to dict and add event_type name
        event_dict = asdict(event)
        event_dict['event_type'] = event.event_type.name
        
        # Handle enums in the dict for serialization
        for key, value in event_dict.items():
            if hasattr(value, 'name'):
                event_dict[key] = value.name
                
        self.events.append(event_dict)

    def save(self, filepath: str) -> None:
        if not self.events:
            print("No events to save.")
            return
            
        df = pd.DataFrame(self.events)
        
        if filepath.endswith('.parquet'):
            df.to_parquet(filepath, index=False)
        elif filepath.endswith('.csv'):
            df.to_csv(filepath, index=False)
        else:
            raise ValueError("Filepath must end with .parquet or .csv")
            
        print(f"Serialized {len(df)} events to {filepath}")
