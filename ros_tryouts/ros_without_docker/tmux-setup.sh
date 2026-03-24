#!/bin/bash

SESSION="ros_agent"

# 1. Iniciar la sesión de tmux (en segundo plano -d)
tmux new-session -d -s $SESSION

# Tab 1: InOrbit agent
tmux rename-window -t $SESSION:0 'InOrbit'

# Tab 2: Extra
tmux new-window -t $SESSION:1 -n 'Extra'

tmux attach-session -t $SESSION