ps aux | grep "backend/unit.py" | grep -v grep | awk '{print $2}' | xargs kill -9
ps aux | grep "backend/balancer.py" | grep -v grep | awk '{print $2}' | xargs kill -9