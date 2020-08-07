## Creating tfrecord  
Execute `python get_shuffled_list_from_vedio.py` to generate a shuffled list of information of all examplar search imge pairs for training.   
Then`python prepare_training_dataset.py` to write the real data into a tfrecord file.
## Training model
`python run_tracker_training.py`   

## Running the tracker
`python run_tracker_evaluation.py`


