from concurrent import futures

import grpc
import envData_pb2
import envData_pb2_grpc

import threading
import pygame
import time

GEM_IMG_PATH = "imgs/gem.png"
FIRE_IMG_PATH = "imgs/fire.png"
OBSTACLE_IMG_PATH = "imgs/obstacle.png"
ROAD_IMG_PATH = "imgs/road.png"
AGENT_IMG_PATH = "imgs/agent2.png"

BASIC_REWARD = -0.1
HIT_REWARD = -1
GEM_REWARD = 30
FIRE_REWARD = -30


def run_server(server):
    server.start()
    server.wait_for_termination()


class Wall(pygame.sprite.Sprite):

    def __init__(self, x, y, width, img_path):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.image.load(img_path).convert()
        self.image = pygame.transform.scale(self.image, (width, width))
        self.rect = self.image.get_rect()
        self.rect.left = x
        self.rect.top = y


class Agent(pygame.sprite.Sprite):

    def __init__(self, pos, width_ratio, wall_width, img_path):
        pygame.sprite.Sprite.__init__(self)
        self.pos = pos
        self.width = int(wall_width * width_ratio)  # agent image width = wall width * width ratio (0 < ratio < 1)
        self.image = pygame.image.load(img_path).convert()
        self.image = pygame.transform.scale(self.image, (self.width, self.width))
        self.image.set_colorkey((255, 255, 255))
        self.rect = self.image.get_rect()
        self.rect.left = pos[0] * wall_width + int((0.5 - width_ratio / 2) * wall_width)
        self.rect.top = pos[1] * wall_width + int((0.5 - width_ratio / 2) * wall_width)
        self.wall_width = wall_width

    def update(self, action_idx):
        move_step = self.wall_width
        # move N
        if action_idx == 0:
            self.pos[1] = self.pos[1] - 1
            self.rect.top -= move_step
        # move E
        elif action_idx == 1:
            self.pos[0] = self.pos[0] + 1
            self.rect.left += move_step
        # move S
        elif action_idx == 2:
            self.pos[1] = self.pos[1] + 1
            self.rect.top += move_step
        # move W
        elif action_idx == 3:
            self.pos[0] = self.pos[0] - 1
            self.rect.left -= move_step
        # Don't move if action_idx is not 0 or 1 or 2 or 3


class Simulator(envData_pb2_grpc.Simulator):

    def __init__(self):

        """
           0 means normal road, 1 means gem(good destination), 
          -1 means fire(bad destination), 
          -2 means obstacle
        """
        self.env_state = [[0, 0, 1],
                          [0, -2, -2],
                          [0, 0, -1]]
        self.initial_pos = [0, 2]  # at the third row, the frist column
        self.wall_width = 160

        # window size depends on the env_state's size.
        pygame.init()
        self.WIN_WIDTH = self.wall_width * len(self.env_state[0])
        self.WIN_HEIGHT = self.wall_width * len(self.env_state)
        self.screen = pygame.display.set_mode((self.WIN_WIDTH, self.WIN_HEIGHT), 0, 32)
        pygame.display.set_caption("gRPC Server@Mars")

        # create wall group and agent group
        self.wall_group = self.get_wall_group(self.wall_width, self.env_state)
        self.agent_group = pygame.sprite.Group()
        self.agent_group.add(Agent(self.initial_pos.copy(), 0.6, self.wall_width, AGENT_IMG_PATH))

    def get_wall_group(self, wall_width, env_state):

        wall_group = pygame.sprite.Group()

        for i in range(len(env_state)):
            for j in range(len(env_state[0])):
                # normal road - green, fire - red, gem - blue, obstacle - gray
                if env_state[i][j] == 0:
                    img_path = ROAD_IMG_PATH
                elif env_state[i][j] == 1:
                    img_path = GEM_IMG_PATH
                elif env_state[i][j] == -1:
                    img_path = FIRE_IMG_PATH
                else:
                    img_path = OBSTACLE_IMG_PATH
                wall = Wall(j * wall_width, i * wall_width, wall_width, img_path)
                wall_group.add(wall)

        return wall_group

    def get_near_item(self, action_idx, pos):
        """
            To get the Item of Agent's N/E/S/W
        """
        if action_idx == 0:
            return self.env_state[pos[1] - 1][pos[0]]
        elif action_idx == 1:
            return self.env_state[pos[1]][pos[0] + 1]
        elif action_idx == 2:
            return self.env_state[pos[1] + 1][pos[0]]
        else:
            return self.env_state[pos[1]][pos[0] - 1]

    def get_current_item(self, pos):
        return self.env_state[pos[1]][pos[0]]

    def getObservation(self, request, context):
        agent = self.agent_group.sprites()[0]

        """
        observation = [if_N_accessible, if_E_accessible, if_S_accessible, if_W_accessible, 
                       if_N_gem, if_E_gem, if_S_gem, if_W_gem,
                       if_N_fire, if_E_fire, if_S_fire, if_W_fire]
        """
        obs_list = [0 for _ in range(12)]

        pos = agent.pos

        # judge N accessible? Has Gem? Has Fire?
        if self.judge_if_action_valid(0, self.env_state, pos):
            obs_list[0] = 1
            if self.get_near_item(0, pos) == 1:
                obs_list[4] = 1
            elif self.get_near_item(0, pos) == -1:
                obs_list[8] = 1

        # judge E accessible? Has Gem? Has Fire?
        if self.judge_if_action_valid(1, self.env_state, pos):
            obs_list[1] = 1
            if self.get_near_item(1, pos) == 1:
                obs_list[5] = 1
            elif self.get_near_item(1, pos) == -1:
                obs_list[9] = 1

        # judge S accessible? Has Gem? Has Fire?
        if self.judge_if_action_valid(2, self.env_state, pos):
            obs_list[2] = 1
            if self.get_near_item(2, pos) == 1:
                obs_list[6] = 1
            elif self.get_near_item(2, pos) == -1:
                obs_list[10] = 1

        # judge W accessible? Has Gem? Has Fire?
        if self.judge_if_action_valid(3, self.env_state, pos):
            obs_list[3] = 1
            if self.get_near_item(3, pos) == 1:
                obs_list[7] = 1
            elif self.get_near_item(3, pos) == -1:
                obs_list[11] = 1

        # get the binary string stream and convert to int
        binary_str = ""
        for obs in obs_list:
            binary_str += str(obs)
        observation_value = int(binary_str, 2)

        return envData_pb2.AgentObservation(ObservationValue=observation_value, AgentPosX=agent.pos[0],
                                            AgentPosY=agent.pos[1])

    def print_test(self):
        print("Run after thread!")

    def render(self, request, context):
        self.wall_group.draw(self.screen)
        self.agent_group.draw(self.screen)
        pygame.display.update()
        return envData_pb2.UpdateResult()

    def local_render(self):
        self.wall_group.draw(self.screen)
        self.agent_group.draw(self.screen)
        pygame.display.flip()

    def judge_if_action_valid(self, action_idx, env_state, current_pos):

        state_height = len(env_state)
        state_width = len(env_state[0])
        # move N
        if action_idx == 0:
            if current_pos[1] == 0 or self.get_near_item(0, current_pos) == -2:
                return False
        # move E
        elif action_idx == 1:
            if current_pos[0] == (state_width - 1) or self.get_near_item(1, current_pos) == -2:
                return False
        # move S
        elif action_idx == 2:
            if current_pos[1] == (state_height - 1) or self.get_near_item(2, current_pos) == -2:
                return False
        # move W
        elif action_idx == 3:
            if current_pos[0] == 0 or self.get_near_item(3, current_pos) == -2:
                return False
        return True

    def step(self, request, context):
        reward = BASIC_REWARD  # basic reward
        agent = self.agent_group.sprites()[0]
        action_idx = request.action_idx
        action_valid = self.judge_if_action_valid(action_idx, self.env_state, agent.pos)

        terminal = False

        if action_valid:
            agent.update(action_idx)
        # else agent won't move and reward += r(hit)
        else:
            reward += HIT_REWARD

        reached_grid = self.get_current_item(agent.pos)
        if reached_grid == 1:
            reward += GEM_REWARD
            terminal = True
        elif reached_grid == -1:
            reward += FIRE_REWARD
            terminal = True

        print("[INFO]Agent takes action: ", action_idx, " - If action valid: ", action_valid, " - reward: ", reward)
        return envData_pb2.StepResult(reward=reward, terminal=terminal)

    def local_step(self):
        reward = BASIC_REWARD  # basic reward
        agent = self.agent_group.sprites()[0]
        action_idx = 1
        action_valid = self.judge_if_action_valid(action_idx, self.env_state, agent.pos)

        terminal = False

        if action_valid:
            agent.update(action_idx)
        # else agent won't move and reward += r(hit)
        else:
            reward += HIT_REWARD

        reached_grid = self.get_current_item(agent.pos)
        if reached_grid == 1:
            reward += GEM_REWARD
            terminal = True
        elif reached_grid == -1:
            reward += FIRE_REWARD
            terminal = True

        print("[INFO]Agent takes action: ", action_idx, " - If action valid: ", action_valid, " - reward: ", reward)
        return (reward, terminal)

    def reset(self, request, context):
        self.agent_group.remove(self.agent_group.sprites()[0])
        self.agent_group.add(Agent(self.initial_pos.copy(), 0.6, self.wall_width, AGENT_IMG_PATH))
        print("[Env]: Env has been reset!")
        return envData_pb2.ResetResult()
    
    def loacal_reset(self):
        self.agent_group.remove(self.agent_group.sprites()[0])
        self.agent_group.add(Agent(self.initial_pos.copy(), 0.6, self.wall_width, AGENT_IMG_PATH))
        print("[Env]: Env has been reset!")


def local_test(simulator):
    while True:
        simulator.local_render()
        r, terminal = simulator.local_step()
        if terminal:
            simulator.loacal_reset()
        time.sleep(0.05)


def serve():
    simulator = Simulator()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    envData_pb2_grpc.add_SimulatorServicer_to_server(simulator, server)
    server.add_insecure_port('[::]:50051')

    t1 = threading.Thread(target=run_server, args=(server,))
    t1.start()

    simulator.print_test()

    # local test
    # local_test(simulator)

    # t1.join()


if __name__ == "__main__":
    serve()
