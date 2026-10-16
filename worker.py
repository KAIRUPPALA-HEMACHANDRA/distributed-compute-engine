import os
from redis import Redis
from rq import Worker, Queue, Connection
from server import handle_request

# Connect to the Redis container across the internal Docker network
redis_conn = Redis(host='redis_queue', port=6379)

if __name__ == '__main__':
    # Boot up the background worker and listen for math tasks
    with Connection(redis_conn):
        worker = Worker(map(Queue, ['default']))
        print("Background worker actively listening to Redis queue...")
        worker.work()
 