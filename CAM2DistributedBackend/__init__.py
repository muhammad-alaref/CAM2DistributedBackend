"""The driver program of Spark

This is the driver program of an analysis submission.

"""

import click

@click.command(help='Make a submission to Spark')
@click.argument('master_url')
@click.argument('namenode_url')
@click.argument('username')
@click.argument('submission_id')
@click.argument('request_file')
@click.argument('analyzer_file')
@click.version_option(prog_name='CAM2DistributedBackend')
def cli(master_url, namenode_url, username, submission_id, request_file, analyzer_file):
	from pyspark import SparkContext, SparkConf
	from CAM2DistributedBackend.camera.camera import IPCamera, StreamFormat
	from CAM2DistributedBackend.util.request import Request
	import time
	
	# Info
	username = username
	submission_id = submission_id
	
	# Setting up the request
	request = Request(request_file)
	
	analysis_class = request.analysis_class
	analysis_duration = request.duration
	frames_limit = request.snapshots_to_keep
	is_video = request.is_video
	interval = request.interval
	
	def run_analyzer(camera):
		# Necessary imports
		from CAM2DistributedBackend.util.storage_client import StorageClient
		from CAM2DistributedBackend.analyzer.camera_metadata import CameraMetadata
		from CAM2DistributedBackend.analyzer.frame_metadata import FrameMetadata
		
		# Initialize a storage client
		storage_client = StorageClient(namenode_url, username, submission_id, camera.id)
		
		# Initialize the analyzer
		import os, importlib
		analyzer_class = getattr(importlib.import_module(os.path.splitext(os.path.basename(analyzer_file))[0]), analysis_class)
		analyzer = analyzer_class()
		analyzer._save = storage_client.save
		analyzer.initialize()
		
		# Initialize the camera
		if is_video:
			stream_format = StreamFormat.MJPEG
		else:
			stream_format = StreamFormat.IMAGE
		camera.open_stream(stream_format)
		
		# Set up initial meta-data
		start_time = time.time()
		frame_sequence_num = 0
		camera_metadata = CameraMetadata(camera.id, camera.latitude, camera.longitude)
		
		# Analysis loop
		while time.time() - start_time < analysis_duration:
			register_time = time.time()
			frame, frame_size = camera.get_frame()
			frame_timestamp = time.time()
			frame_metadata = FrameMetadata(camera_metadata, frame_sequence_num, frame_timestamp)
			analyzer._add_frame(frame, frame_metadata, frames_limit)
			analyzer.on_new_frame()
			frame_sequence_num += 1
			time.sleep(max(0, register_time + interval - time.time()))
		
		# Finalize
		camera.close_stream()
		analyzer.finalize()
	
	# Prepare the cameras
	cameras = request.cameras
	
	# Initialize Spark
	master_url = master_url	# For local mode: 'local[{}]'.format(len(cameras))
	conf = SparkConf().setAppName('CAM2').setMaster(master_url).set('spark.cores.max', len(cameras))
	ctx = SparkContext(conf=conf)
	ctx.addPyFile(analyzer_file)
	ctx.setLogLevel('ALL')
	
	# Submit the analysis job
	distributedCameras = ctx.parallelize(cameras, len(cameras))
	distributedCameras.foreach(run_analyzer)
