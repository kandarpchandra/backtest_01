import pandas as pd
from dataclasses import asdict
from typing import List, Dict
from backtester.events.types import BaseEvent
import os
from enum import Enum

class EventSerializer:
    """
    Records every event in the backtest and flushes to disk in chunks 
    to prevent memory explosion on large datasets.
    """
    def __init__(self, filepath: str = "event_log.parquet", chunk_size: int = 100000):
        self.events: List[Dict] = []
        self.filepath = filepath
        self.chunk_size = chunk_size
        self._is_first_chunk = True
        
        # Clear existing file
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    def log_event(self, event: BaseEvent) -> None:
        # Convert dataclass to dict and add event_type name
        event_dict = asdict(event)
        event_dict['event_type'] = event.event_type.name
        
        # Handle enums in the dict for serialization safely
        for key, value in event_dict.items():
            if isinstance(value, Enum):
                event_dict[key] = value.name
                
        self.events.append(event_dict)
        
        if len(self.events) >= self.chunk_size:
            self.flush()

    def flush(self) -> None:
        if not self.events:
            return
            
        df = pd.DataFrame(self.events)
        
        if self.filepath.endswith('.parquet'):
            # Parquet appending using fastparquet (requires fastparquet installed)
            # For simplicity in this engine without heavy dependencies, we'll append to CSV
            # or recreate the parquet. Given it's a mock, we'll append to Parquet if fastparquet is used,
            # but to be safe and dependency-free, let's just write/append CSV for the chunked mode,
            # or use PyArrow append. Pyarrow dataset append is standard.
            import pyarrow as pa
            import pyarrow.parquet as pq
            table = pa.Table.from_pandas(df)
            if self._is_first_chunk:
                pq.write_table(table, self.filepath)
                self._is_first_chunk = False
            else:
                # To truly append parquet efficiently requires writing multiple files to a directory
                # or reading the old one. We'll read and rewrite for now to keep the single file API,
                # though directory partitioning is better.
                existing_table = pq.read_table(self.filepath)
                combined = pa.concat_tables([existing_table, table])
                pq.write_table(combined, self.filepath)
        elif self.filepath.endswith('.csv'):
            mode = 'w' if self._is_first_chunk else 'a'
            header = self._is_first_chunk
            df.to_csv(self.filepath, mode=mode, header=header, index=False)
            self._is_first_chunk = False
        else:
            raise ValueError("Filepath must end with .parquet or .csv")
            
        self.events.clear()

    def save(self, filepath: str = None) -> None:
        """Flushes any remaining events. (filepath arg kept for backward compatibility but ignored)"""
        self.flush()
