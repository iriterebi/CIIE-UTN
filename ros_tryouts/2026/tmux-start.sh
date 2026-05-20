#!/bin/bash

SESSION="ros_agent_session"
WORK_DIR="/root/workspace/ros_tryouts/2026"
ROS_SETUP="source /opt/ros/jazzy/setup.bash"

# Kill any existing session with the same name
tmux kill-session -t $SESSION 2>/dev/null || true
tmux new-session -d -s $SESSION

# Window 0: InOrbit agent
tmux rename-window -t $SESSION:0 "InOrbit"
tmux send-keys -t $SESSION:0 "$ROS_SETUP && curl https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN | sh" Enter

# Window 1: Arduino serial scraper
tmux new-window -t $SESSION:1 -n "Serial"
tmux send-keys -t $SESSION:1 "$ROS_SETUP && cd ${WORK_DIR}/agent/serial_scraper/ && python3 scraper.py" Enter

# Window 2: Listener
# tmux new-window -t $SESSION:2 -n "Listener"
# tmux send-keys -t $SESSION:2 "$ROS_SETUP && cd ${WORK_DIR}/agent/ && python3 listener.py" Enter

# Window 3: Camera node
# tmux new-window -t $SESSION:3 -n "Camera"
# tmux send-keys -t $SESSION:3 "$ROS_SETUP && cd ${WORK_DIR}/agent/camera/ && python3 camera_node.py" Enter

# Window 4: Interactive terminal
tmux new-window -t $SESSION:2 -n "Terminal"

tmux attach-session -t $SESSION
