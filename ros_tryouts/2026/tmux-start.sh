#!/bin/bash

SESSION="ros_agent_session"

tmux new-session -d -s $SESSION

tmux rename-window -t $SESSION:0 "InOrbit"
tmux send-keys -t $SESSION:0 "export ROS_DOMAIN_ID=0 && curl https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN | sh" Enter

tmux new-window -t $SESSION:1 -n "Extra tab"

tmux attach-session -t $SESSION