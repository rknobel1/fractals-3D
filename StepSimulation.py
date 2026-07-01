import copy
from collections import deque

class SimulationCancelled(Exception):
    pass

def _raise_if_cancelled(cancel_callback):
    if cancel_callback is not None and cancel_callback():
        raise SimulationCancelled()

# Stores all the hard reset tiles
hard_reset_tiles = []

def get_tag(x, y, z):
        return str(x) + ',' + str(y) + ',' + str(z)

# Step-mode snapshot recording. This is enabled only while run_step_simulation runs.
_step_snapshots = None

def _serialize_tile_value(value):
    if isinstance(value, Tile):
        return value.id

    return value


def _tile_snapshot(tile):
    return {
        key: _serialize_tile_value(value)
        for key, value in vars(tile).items()
        if not key.startswith("_")
    }

def record_tile_placement(placed_tile, placing_tile):
    if _step_snapshots is None:
        return

    if placed_tile.x is None or placed_tile.y is None or placed_tile.z is None:
        return

    _step_snapshots.append({
        "type": "attachment",
        "placed_tile": _tile_snapshot(placed_tile),
        "placing_tile": _tile_snapshot(placing_tile),
    })

def record_transition_snapshots(before_a, before_b, after_a, after_b, explanation):
    if _step_snapshots is None:
        return

    _step_snapshots.append({
        "type": "transition",
        "before": [before_a, before_b],
        "after": [after_a, after_b],
        "explanation": explanation
    })

def record_transition(before_tile_1, before_tile_2,
                      after_tile_1, after_tile_2):
    if _step_snapshots is None:
        return

    # Both tiles should already exist in the assembly.
    if (before_tile_1.x is None or before_tile_2.x is None or
        after_tile_1.x is None or after_tile_2.x is None):
        return

    _step_snapshots.append({
        "type": "transition",
        "before": [
            _tile_snapshot(before_tile_1),
            _tile_snapshot(before_tile_2),
        ],
        "after": [
            _tile_snapshot(after_tile_1),
            _tile_snapshot(after_tile_2),
        ],
    })

class Tile():

    def __init__(self, p, n, x=None, y=None, z=None):
        object.__setattr__(self, "_suspend_notifications", True)

        # Strictly for frontend
        self.id = get_tag(x, y, z)
        self.x = x
        self.y = y
        self.z = z
        # --------------------

        self.previous = p
        self.next = n

        # What direction to copy
        self.copy_direction = None

        # Caps
        self.caps = []

        # Local tile information (and neighbors)
        self.status = None
        self.tile_to_N = None
        self.tile_to_E = None
        self.tile_to_W = None
        self.tile_to_S = None
        self.tile_to_U = None
        self.tile_to_D = None

        # If tile becomes new key tile or not
        self.new_kt_N = False
        self.new_kt_E = False
        self.new_kt_W = False
        self.new_kt_S = False
        self.new_kt_U = False
        self.new_kt_D = False

        # Breadcrumb trail
        self.N = None
        self.E = None
        self.W = None
        self.S = None
        self.U = None
        self.D = None

        # Holds information from breadcrumb trail (what the state was before)
        self.temp = None

        # What is being transferred
        self.transfer = None

        # If tile is a seed
        self.original_seed = False
        self.pseudo_seed = False

        # If tile is on edge of sub-assembly
        self.wall = False

        # Direction to key tile
        self.key_tile_N = None
        self.key_tile_E = None
        self.key_tile_W = None
        self.key_tile_S = None
        self.key_tile_U = None
        self.key_tile_D = None

        # Has assembly been copied for tile
        self.copied = False

        # Is tile terminal
        self.terminal = False

        # For seeds, number of times subassembly has been copied
        self.num_times_copied = 0

        # The new previous and next for tile
        self.new_p = None
        self.new_n = None

        # If first tile copied
        self.first_tile = False
    
    def set_id(self):
        self.id = get_tag(self.x, self.y, self.z)
        return self.id

def debug_print(t):
    print("Previous: ", t.previous)
    print("Next: ", t.next)

    # What direction to copy
    print("Copy direction: ", t.copy_direction)

    # Caps
    print("Caps: ", t.caps)

    # Local tile information (and neighbors)
    print("Status: ", t.status)
    print("Tile to N: ", t.tile_to_N)
    print("Tile to E: ", t.tile_to_E)
    print("Tile to W: ", t.tile_to_W)
    print("Tile to S: ", t.tile_to_S)
    print("Tile to U: ", t.tile_to_U)
    print("Tile to D: ", t.tile_to_D)

    # If tile becomes new key tile or not
    print("Becomes Key Tile N: ", t.new_kt_N)
    print("Becomes Key Tile E: ", t.new_kt_E)
    print("Becomes Key Tile W: ", t.new_kt_W)
    print("Becomes Key Tile S: ", t.new_kt_S)
    print("Becomes Key Tile U: ", t.new_kt_U)
    print("Becomes Key Tile D: ", t.new_kt_D)

    # Breadcrumb trail
    print("N: ", t.N)
    print("E: ", t.E)
    print("W: ", t.W)
    print("S: ", t.S)
    print("U: ", t.U)
    print("D: ", t.D)

    # Holds information from breadcrumb trail (what the state was before)
    print("Temp: ", t.temp)

    # What is being transferred
    print("Transfer: ", t.transfer)

    # If tile is a seed
    print("Original Seed: ", t.original_seed)
    print("Pseudo Seed: ", t.pseudo_seed)

    # If tile is on edge of sub-assembly
    print("Wall: ", t.wall)

    # Direction to key tile
    print("Direction to KT N: ", t.key_tile_N)
    print("Direction to KT E: ", t.key_tile_E)
    print("Direction to KT W: ", t.key_tile_W)
    print("Direction to KT S: ", t.key_tile_S)
    print("Direction to KT U: ", t.key_tile_U)
    print("Direction to KT D: ", t.key_tile_D)

    # Has assembly been copied for tile
    print("Copied: ", t.copied)

    # Is tile terminal
    print("Terminal: ", t.terminal)

    # For seeds, number of times subassembly has been copied
    print("Number of Times Copied: ", t.num_times_copied)

    # The new previous and next for tile
    print("New Previous: ", t.new_p)
    print("New Next: ", t.new_n)

    # If first tile copied
    print("First Tile: ", t.first_tile)

# Functions -----------------------------------
# Returns len(next)
def num_next(tile):
    if tile.next == None: return 0
    else: return len(tile.next)

# RETURNS: opp(d) i.e if N -> S
def opp(d):
    if d == "N": 
        return "S"
    if d == "E": 
        return "W"
    if d == "W": 
        return "E"
    if d == "S": 
        return "N"
    if d == "U": 
        return "D"
    if d == "D":
        return "U"
    
# RETURNS: direction of breadcrumb trail (how to retrace signal)
def breadcrumb_trail(tile): 
    if tile.N == 'W' or tile.N == 'M':
        return 'N'
    if tile.E == 'W' or tile.E == 'M':
        return 'E'
    if tile.W == 'W' or tile.W == 'M':
        return 'W'
    if tile.S == 'W' or tile.S == 'M':
        return 'S'
    if tile.U == 'W' or tile.U == 'M':
        return 'U'
    if tile.D == 'W' or tile.D == 'M':
        return 'D'
    
# RETURNS: adjacent tile in direction d from current tile
def retrieve_tile(tile, d):
    if (d == "N"):
        return tile.tile_to_N
    if (d == "E"):
        return tile.tile_to_E
    if (d == "W"):
        return tile.tile_to_W
    if (d == "S"):
        return tile.tile_to_S
    if (d == "U"):
        return tile.tile_to_U
    if (d == "D"):
        return tile.tile_to_D
    
# RETURNS: whether subassembly is completed or ont
def is_assembly_finished(tile):
    if tile.N == 'N':
        return False
    if tile.E == 'N':
        return False
    if tile.W == 'N':
        return False
    if tile.S == 'N':
        return False
    if tile.U == 'N':
        return False
    if tile.D == 'N':
        return False
    
    return True

def copy_direction_update_tiles(cur_tile, direction):
    c = 0
    if cur_tile.next != None: c += len(cur_tile.next)
    if cur_tile.previous != None: c += len(cur_tile.previous)
    if not cur_tile.original_seed or not cur_tile.pseudo_seed: c -= 1 

    if not cur_tile.terminal and not (cur_tile.original_seed or cur_tile.pseudo_seed): cur_tile.copy_direction = direction + str(c)
    else: cur_tile.copy_direction = direction

    if cur_tile.new_n == None and cur_tile.new_p == None: 
        cur_tile.new_n = copy.deepcopy(cur_tile.next)
        cur_tile.new_p = copy.deepcopy(cur_tile.previous)

    cur_tile.status = 'P'
    cur_tile.caps = []

    if cur_tile.N != None and cur_tile.key_tile_N != None: cur_tile.N = 'N'
    else: cur_tile.N = None
    if cur_tile.E != None and cur_tile.key_tile_E != None: cur_tile.E = 'N'
    else: cur_tile.E = None
    if cur_tile.W != None and cur_tile.key_tile_W != None: cur_tile.W = 'N'
    else: cur_tile.W = None
    if cur_tile.S != None and cur_tile.key_tile_S != None: cur_tile.S = 'N'
    else: cur_tile.S = None
    if cur_tile.U != None and cur_tile.key_tile_U != None: cur_tile.U = 'N'
    else: cur_tile.U = None
    if cur_tile.D != None and cur_tile.key_tile_D != None: cur_tile.D = 'N'
    else: cur_tile.D = None

# Proprogate copy direction through subassembly
def choose_copy_direction(tile, direction, cancel_callback=None):
    _raise_if_cancelled(cancel_callback)
    stack = deque()
    stack.append(tile)
    visited_tiles = []

    t = []

    while len(stack) > 0:
        cur_tile = stack.pop()

        if cur_tile.next != None:
            for neighbor in cur_tile.next:
                if retrieve_tile(cur_tile, neighbor) not in visited_tiles and retrieve_tile(cur_tile, neighbor) != None:
                    adj_tile = retrieve_tile(cur_tile, neighbor)
                    stack.append(adj_tile)

                    before_a, before_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)

                    copy_direction_update_tiles(cur_tile, direction)
                    copy_direction_update_tiles(adj_tile, direction)

                    after_a, after_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)
                    record_transition_snapshots(before_a, before_b, after_a, after_b, "Propagating copy direction")

        if cur_tile.previous != None:
            for neighbor in cur_tile.previous:
                if retrieve_tile(cur_tile, neighbor) not in visited_tiles and retrieve_tile(cur_tile, neighbor) != None:
                    adj_tile = retrieve_tile(cur_tile, neighbor)
                    stack.append(adj_tile)

                    before_a, before_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)

                    copy_direction_update_tiles(cur_tile, direction)
                    copy_direction_update_tiles(adj_tile, direction)

                    after_a, after_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)
                    record_transition_snapshots(before_a, before_b, after_a, after_b, "Propagating copy direction")

        if cur_tile.terminal:
            t.append(cur_tile)

        visited_tiles.append(cur_tile)

    # All tiles are marked with copying direction, retrace back to original/pseudo seed
    while len(t) > 0:
        cur_tile = t.pop()

        if cur_tile.next != None:
            for neighbor in cur_tile.next:
                if len(retrieve_tile(cur_tile, neighbor).copy_direction) > 1:
                    adj_tile = retrieve_tile(cur_tile, neighbor)

                    before_a, before_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)

                    l = list(adj_tile.copy_direction)

                    l[1] = int(l[1]) - 1

                    if l[1] == 0:
                        adj_tile.copy_direction = l[0]
                        t.append(adj_tile)
                        after_a, after_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Retrace to Original/Pseudo Seed")
                    else:
                        l[1] = str(l[1])
                        adj_tile.copy_direction = "".join(l)
                        after_a, after_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Retrace to Original/Pseudo Seed")
                        break

        if cur_tile.previous != None:
            for neighbor in cur_tile.previous:
                if len(retrieve_tile(cur_tile, neighbor).copy_direction) > 1:
                    adj_tile = retrieve_tile(cur_tile, neighbor)

                    before_a, before_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)

                    l = list(adj_tile.copy_direction)

                    l[1] = int(l[1]) - 1

                    if l[1] == 0:
                        adj_tile.copy_direction = l[0]
                        t.append(adj_tile)
                        after_a, after_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Retrace to Original/Pseudo Seed")
                    else:
                        l[1] = str(l[1])
                        adj_tile.copy_direction = "".join(l)
                        after_a, after_b = _tile_snapshot(cur_tile), _tile_snapshot(adj_tile)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Retrace to Original/Pseudo Seed")
                        break

    return

# Updates prev/next if tile is missing
def update_prev_next(ct):

    if ct.tile_to_N != None: ct.N = 'N'
    if ct.tile_to_E != None: ct.E = 'N'
    if ct.tile_to_W != None: ct.W = 'N'
    if ct.tile_to_S != None: ct.S = 'N'
    if ct.tile_to_U != None: ct.U = 'N'
    if ct.tile_to_D != None: ct.D = 'N'

    ct.next = copy.deepcopy(ct.new_n)
    ct.previous = copy.deepcopy(ct.new_p)

# Reset specific tile
def reset_tile(ct):

    # Reset current tile info
    ct.copy_direction = None
    ct.status = None
    ct.wall = False
    ct.pseudo_seed = False
    ct.caps = []
    ct.copied = False
    ct.num_times_copied = 0
    ct.temp = None
    ct.transfer = None

    ct.new_n = None
    ct.new_p = None
    ct.first_tile = False

    if num_next(ct)+1 == 1: ct.terminal = True
    else: ct.terminal = False

# Hard reset only using terminal tiles:
def hard_reset(cancel_callback=None):
    _raise_if_cancelled(cancel_callback)

    while len(hard_reset_tiles) > 0:

        ct = hard_reset_tiles.pop()
        # Retrieve adjacent tile
        adj_tile = retrieve_tile(ct, ct.new_p[0])

        before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
        update_prev_next(ct)
        update_prev_next(adj_tile)
        after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
        record_transition_snapshots(before_a, before_b, after_a, after_b, "Updating prev/next")

        # Start by first spreading hard reset if not yet done
        if adj_tile.copy_direction == 'r': 
            before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
            adj_tile.copy_direction = 'R?'
            t = [adj_tile]
            update_prev_next(adj_tile)
            after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Propagating hard reset signal")

            while len(t) > 0:
                cur = t.pop()

                if cur.next != None: 
                    for neighbor in cur.next:
                        a = retrieve_tile(cur, neighbor)
                        before_a, before_b = _tile_snapshot(cur), _tile_snapshot(a)
                        update_prev_next(a)
                        if a != None and (a.copy_direction == 'r'):
                            if a.next == None: 
                                a.copy_direction = 'R'
                                hard_reset_tiles.append(a)
                            else: a.copy_direction = 'R?'
                            t.append(a)

                        cur.key_tile_N = '*'
                        cur.key_tile_E = '*'
                        cur.key_tile_W = '*'
                        cur.key_tile_S = '*'
                        cur.key_tile_U = '*'
                        cur.key_tile_D = '*'

                        if num_next(cur) == 0: cur.copy_direction = 'R'
                        else: cur.copy_direction = 'R' + str(num_next(cur))

                        after_a, after_b = _tile_snapshot(cur), _tile_snapshot(a)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Propagating hard reset signal")

                if cur.previous != None: 
                    for neighbor in cur.previous:
                        a = retrieve_tile(cur, neighbor)
                        before_a, before_b = _tile_snapshot(cur), _tile_snapshot(a)
                        update_prev_next(a)
                        if a != None and (a.copy_direction == 'r'):
                            if a.next == None: 
                                a.copy_direction = 'R'
                                hard_reset_tiles.append(a)
                            else: a.copy_direction = 'R?'
                            t.append(a)

                        cur.key_tile_N = '*'
                        cur.key_tile_E = '*'
                        cur.key_tile_W = '*'
                        cur.key_tile_S = '*'
                        cur.key_tile_U = '*'
                        cur.key_tile_D = '*'

                        if num_next(cur) == 0: cur.copy_direction = 'R'
                        else: cur.copy_direction = 'R' + str(num_next(cur))

                        after_a, after_b = _tile_snapshot(cur), _tile_snapshot(a)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Propagating hard reset signal")

        before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
        # Resetting tile
        reset_tile(ct)
        after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
        record_transition_snapshots(before_a, before_b, after_a, after_b, "Hard resetting")

        before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
        # Not at seed yet
        if not adj_tile.original_seed: 
            
            # Update direction to key tiles for cur tile and neighbor
            #   When cur_tile is terminal
            if ct.terminal:
                if ct.new_kt_N: 
                    ct.key_tile_N = None
                    adj_tile.key_tile_N = opp(ct.previous[0])
                else: ct.key_tile_N = ct.previous[0]

                if ct.new_kt_E: 
                    ct.key_tile_E = None
                    adj_tile.key_tile_E = opp(ct.previous[0])
                else: ct.key_tile_E = ct.previous[0]

                if ct.new_kt_W: 
                    ct.key_tile_W = None
                    adj_tile.key_tile_W = opp(ct.previous[0])
                else: ct.key_tile_W = ct.previous[0]

                if ct.new_kt_S: 
                    ct.key_tile_S = None
                    adj_tile.key_tile_S = opp(ct.previous[0])
                else: ct.key_tile_S = ct.previous[0]

                if ct.new_kt_U: 
                    ct.key_tile_U = None
                    adj_tile.key_tile_U = opp(ct.previous[0])
                else: ct.key_tile_U = ct.previous[0]

                if ct.new_kt_D: 
                    ct.key_tile_D = None
                    adj_tile.key_tile_D = opp(ct.previous[0])
                else: ct.key_tile_D = ct.previous[0]

            #   Cur_tile is not terminal
            else:
                if ct.new_kt_N: 
                    ct.key_tile_N = None
                    adj_tile.key_tile_N = opp(ct.previous[0])
                elif ct.key_tile_N != ct.previous[0]: adj_tile.key_tile_N = opp(ct.previous[0])

                if ct.new_kt_E or (ct.original_seed and ct.key_tile_E == None): 
                    ct.key_tile_E = None
                    adj_tile.key_tile_E = opp(ct.previous[0])
                elif ct.key_tile_E != ct.previous[0]: adj_tile.key_tile_E = opp(ct.previous[0])

                if ct.new_kt_W or (ct.original_seed and ct.key_tile_W == None): 
                    ct.key_tile_W = None
                    adj_tile.key_tile_W = opp(ct.previous[0])
                elif ct.key_tile_W != ct.previous[0]: adj_tile.key_tile_W = opp(ct.previous[0])
                
                if ct.new_kt_S or (ct.original_seed and ct.key_tile_S == None): 
                    ct.key_tile_S = None
                    adj_tile.key_tile_S = opp(ct.previous[0])
                elif ct.key_tile_S != ct.previous[0]: adj_tile.key_tile_S = opp(ct.previous[0])

                if ct.new_kt_U or (ct.original_seed and ct.key_tile_U == None): 
                    ct.key_tile_U = None
                    adj_tile.key_tile_U = opp(ct.previous[0])
                elif ct.key_tile_U != ct.previous[0]: adj_tile.key_tile_U = opp(ct.previous[0])

                if ct.new_kt_D or (ct.original_seed and ct.key_tile_D == None): 
                    ct.key_tile_D = None
                    adj_tile.key_tile_D = opp(ct.previous[0])
                elif ct.key_tile_D != ct.previous[0]: adj_tile.key_tile_D = opp(ct.previous[0])

            # Update adjacent
            l = list(adj_tile.copy_direction)
            l[1] = int(l[1]) - 1

            if adj_tile.original_seed: 
                # Reset the seed
                reset_tile(adj_tile)
                
                if adj_tile.key_tile_N == '*': adj_tile.key_tile_N = None 
                if adj_tile.key_tile_E == '*': adj_tile.key_tile_E = None 
                if adj_tile.key_tile_W == '*': adj_tile.key_tile_W = None 
                if adj_tile.key_tile_S == '*': adj_tile.key_tile_S = None 
                if adj_tile.key_tile_U == '*': adj_tile.key_tile_U = None
                if adj_tile.key_tile_D == '*': adj_tile.key_tile_D = None

            elif l[1]+1 == 1 and adj_tile.previous != None: 

                if adj_tile.key_tile_N == '*': adj_tile.key_tile_N = adj_tile.previous[0]
                if adj_tile.key_tile_E == '*': adj_tile.key_tile_E = adj_tile.previous[0]
                if adj_tile.key_tile_W == '*': adj_tile.key_tile_W = adj_tile.previous[0]
                if adj_tile.key_tile_S == '*': adj_tile.key_tile_S = adj_tile.previous[0]
                if adj_tile.key_tile_U == '*': adj_tile.key_tile_U = adj_tile.previous[0]
                if adj_tile.key_tile_D == '*': adj_tile.key_tile_D = adj_tile.previous[0]
                adj_tile.copy_direction = 'R'
                hard_reset_tiles.append(adj_tile)
            elif l[1]+1 == 1 and adj_tile.previous == None: 
                update_prev_next(adj_tile)
                
                if adj_tile.key_tile_N == '*': adj_tile.key_tile_N = adj_tile.previous[0]
                if adj_tile.key_tile_E == '*': adj_tile.key_tile_E = adj_tile.previous[0]
                if adj_tile.key_tile_W == '*': adj_tile.key_tile_W = adj_tile.previous[0]
                if adj_tile.key_tile_S == '*': adj_tile.key_tile_S = adj_tile.previous[0]
                if adj_tile.key_tile_U == '*': adj_tile.key_tile_U = adj_tile.previous[0]
                if adj_tile.key_tile_D == '*': adj_tile.key_tile_D = adj_tile.previous[0]
                adj_tile.copy_direction = 'R'
                hard_reset_tiles.append(adj_tile)
            else: 
                l[1] = str(l[1])
                adj_tile.copy_direction = "".join(l) 

            ct.new_kt_N = False
            ct.new_kt_E = False
            ct.new_kt_W = False
            ct.new_kt_S = False
            ct.new_kt_U = False
            ct.new_kt_D = False

        else:
            if ct.terminal:
                if ct.new_kt_N: 
                    ct.key_tile_N = None
                    adj_tile.key_tile_N = opp(ct.previous[0])
                else: ct.key_tile_N = ct.previous[0]

                if ct.new_kt_E: 
                    ct.key_tile_E = None
                    adj_tile.key_tile_E = opp(ct.previous[0])
                else: ct.key_tile_E = ct.previous[0]

                if ct.new_kt_W: 
                    ct.key_tile_W = None
                    adj_tile.key_tile_W = opp(ct.previous[0])
                else: ct.key_tile_W = ct.previous[0]

                if ct.new_kt_S: 
                    ct.key_tile_S = None
                    adj_tile.key_tile_S = opp(ct.previous[0])
                else: ct.key_tile_S = ct.previous[0]

                if ct.new_kt_U: 
                    ct.key_tile_U = None
                    adj_tile.key_tile_U = opp(ct.previous[0])
                else: ct.key_tile_U = ct.previous[0]

                if ct.new_kt_D: 
                    ct.key_tile_D = None
                    adj_tile.key_tile_D = opp(ct.previous[0])
                else: ct.key_tile_D = ct.previous[0]
            else: 
                if ct.new_kt_N: 
                    ct.key_tile_N = None
                    adj_tile.key_tile_N = opp(ct.previous[0])
                elif ct.key_tile_N != ct.previous[0]: adj_tile.key_tile_N = opp(ct.previous[0])

                if ct.new_kt_E or (ct.original_seed and ct.key_tile_E == None): 
                    ct.key_tile_E = None
                    adj_tile.key_tile_E = opp(ct.previous[0])
                elif ct.key_tile_E != ct.previous[0]: adj_tile.key_tile_E = opp(ct.previous[0])

                if ct.new_kt_W or (ct.original_seed and ct.key_tile_W == None): 
                    ct.key_tile_W = None
                    adj_tile.key_tile_W = opp(ct.previous[0])
                elif ct.key_tile_W != ct.previous[0]: adj_tile.key_tile_W = opp(ct.previous[0])
                
                if ct.new_kt_S or (ct.original_seed and ct.key_tile_S == None): 
                    ct.key_tile_S = None
                    adj_tile.key_tile_S = opp(ct.previous[0])
                elif ct.key_tile_S != ct.previous[0]: adj_tile.key_tile_S = opp(ct.previous[0])

                if ct.new_kt_U or (ct.original_seed and ct.key_tile_U == None): 
                    ct.key_tile_U = None
                    adj_tile.key_tile_U = opp(ct.previous[0])
                elif ct.key_tile_U != ct.previous[0]: adj_tile.key_tile_U = opp(ct.previous[0])

                if ct.new_kt_D or (ct.original_seed and ct.key_tile_D == None): 
                    ct.key_tile_D = None
                    adj_tile.key_tile_D = opp(ct.previous[0])
                elif ct.key_tile_D != ct.previous[0]: adj_tile.key_tile_D = opp(ct.previous[0])

            # Update adjacent
            l = list(adj_tile.copy_direction)
            l[1] = int(l[1]) - 1

            if l[1]+1 == 1:
                reset_tile(adj_tile)
                
                if adj_tile.key_tile_N == '*': adj_tile.key_tile_N = None 
                if adj_tile.key_tile_E == '*': adj_tile.key_tile_E = None 
                if adj_tile.key_tile_W == '*': adj_tile.key_tile_W = None 
                if adj_tile.key_tile_S == '*': adj_tile.key_tile_S = None 
                if adj_tile.key_tile_U == '*': adj_tile.key_tile_U = None
                if adj_tile.key_tile_D == '*': adj_tile.key_tile_D = None  
            else: 
                l[1] = str(l[1])
                adj_tile.copy_direction = "".join(l)

        after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
        record_transition_snapshots(before_a, before_b, after_a, after_b, "Update key tile directions")

# RETURNS: bool for whether caps on tile should be moved
def move_caps(tile): 
    if tile.wall: return False

    total = 0
    if tile.next != None: 
        total += len(tile.next)

    if tile.previous != None: 
        total += len(tile.previous)

    if len(tile.caps) == (total - 1): return True
    return False

# RETURNS: Number of subassemblies completed - total number of subassemblies attached to tile
def directions_missing(tile):
    total, count = 0, 0

    if tile.N != None: total += 1
    if tile.E != None: total += 1
    if tile.W != None: total += 1
    if tile.S != None: total += 1
    if tile.U != None: total += 1
    if tile.D != None: total += 1

    if tile.N == 'Y': count += 1
    if tile.E == 'Y': count += 1
    if tile.W == 'Y': count += 1
    if tile.S == 'Y': count += 1
    if tile.U == 'Y': count += 1
    if tile.D == 'Y': count += 1

    return total - count

# RETURNS: Direction to incomplete subassembly
def direction_missing(tile):
    if tile.N == 'N': 
        return 'N'
    if tile.E == 'N': 
        return 'E'
    if tile.W == 'N': 
        return 'W'
    if tile.S == 'N': 
        return 'S'
    if tile.U == 'N': 
        return 'U'
    if tile.D == 'N': 
        return 'D'
    
    return 'DONE'

# Returns len(next) + len(prev)
def num_dirs(tile):
    total = 0
    if tile.next != None: 
        total += len(tile.next)
    if tile.previous != None: 
        total += len(tile.previous)

    return total

# Returns len(previous)
def num_prev(tile):
    if tile.previous == None: return 0
    else: return 1

# Copies a tile from current location to new subassembly
def copy_tile(tile, d, ps):
    pseudo_seed = None

    if tile.previous != None:
        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(retrieve_tile(tile, tile.previous[0]))
    else:
        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(retrieve_tile(tile, tile.next[0]))

    tile.status = "W"

    new_info = []

    if tile.next != None: 
        for i in tile.next: new_info.append(i)
    if tile.previous != None:
        new_info.append(tile.previous[0])

    tile_to_copy = Tile(None, new_info)

    tile_to_copy.key_tile_N = tile.key_tile_N
    tile_to_copy.key_tile_E = tile.key_tile_E
    tile_to_copy.key_tile_W = tile.key_tile_W
    tile_to_copy.key_tile_S = tile.key_tile_S
    tile_to_copy.key_tile_U = tile.key_tile_U
    tile_to_copy.key_tile_D = tile.key_tile_D

    tile_to_copy.terminal = tile.terminal
    tile_to_copy.caps = []

    if tile == ps: 
        tile_to_copy.pseudo_seed = True

        if tile.key_tile_N == None: tile_to_copy.new_kt_N = True
        if tile.key_tile_E == None: tile_to_copy.new_kt_E = True
        if tile.key_tile_W == None: tile_to_copy.new_kt_W = True
        if tile.key_tile_S == None: tile_to_copy.new_kt_S = True
        if tile.key_tile_U == None: tile_to_copy.new_kt_U = True
        if tile.key_tile_D == None: tile_to_copy.new_kt_D = True
    else: 
        tile_to_copy.new_kt_N = False
        tile_to_copy.new_kt_E = False
        tile_to_copy.new_kt_W = False
        tile_to_copy.new_kt_S = False
        tile_to_copy.new_kt_U = False
        tile_to_copy.new_kt_D = False

    if tile.original_seed: 
        if tile.key_tile_N == None: tile.new_kt_N = True
        if tile.key_tile_E == None: tile.new_kt_E = True
        if tile.key_tile_W == None: tile.new_kt_W = True
        if tile.key_tile_S == None: tile.new_kt_S = True
        if tile.key_tile_U == None: tile.new_kt_U = True
        if tile.key_tile_D == None: tile.new_kt_D = True

        tile.copied = True
        tile_to_copy.copied = True

    if tile.copied == True: tile_to_copy.copied = True

    tile.transfer = tile_to_copy

    after_a = _tile_snapshot(tile)
    record_transition_snapshots(before_a, before_b, after_a, before_b, "Copying tile")
    
    # North
    if d == "N":
        while tile.key_tile_N != None:
            neighbor = retrieve_tile(tile, tile.key_tile_N[0])

            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

            neighbor.transfer = tile.transfer
            tile.transfer = None

            if tile.key_tile_N[0] == 'N': 
                neighbor.temp = neighbor.S
                neighbor.S = 'W'
            if tile.key_tile_N[0] == 'E': 
                neighbor.temp = neighbor.W
                neighbor.W = 'W'
            if tile.key_tile_N[0] == 'W': 
                neighbor.temp = neighbor.E
                neighbor.E = 'W'
            if tile.key_tile_N[0] == 'S':
                neighbor.temp = neighbor.N 
                neighbor.N = 'W'
            if tile.key_tile_N[0] == 'U':
                neighbor.temp = neighbor.D 
                neighbor.D = 'W'
            if tile.key_tile_N[0] == 'D':
                neighbor.temp = neighbor.U 
                neighbor.U = 'W'

            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = neighbor

        if tile.tile_to_N == None:
            tile_to_place = tile.transfer
            if "S" in tile_to_place.next:
                tile_to_place.next.remove("S")
            if len(tile_to_place.next) == 0: tile_to_place.next = None 
            tile.tile_to_N = tile_to_place
            tile_to_place.tile_to_S = tile

            tile.N, tile_to_place.S = None, 'N'

            tile.wall, tile_to_place.wall = True, True

            if tile.key_tile_S[0] == 'N': tile.N = 'M'
            if tile.key_tile_S[0] == 'E': tile.E = 'M'
            if tile.key_tile_S[0] == 'W': tile.W = 'M'
            if tile.key_tile_S[0] == 'S': tile.S = 'M'
            if tile.key_tile_S[0] == 'U': tile.U = 'M'
            if tile.key_tile_S[0] == 'D': tile.D = 'M'

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['S']
            if tile.new_n == None: tile.new_n = ['N']
            else: tile.new_n.append('N')

            tile_to_place.x = tile.x
            tile_to_place.y = tile.y + 1
            tile_to_place.z = tile.z
            tile_to_place.set_id()
            record_tile_placement(tile_to_place, tile)

        else: 
            adj_tile = tile.tile_to_N
            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            adj_tile.S = 'W'
            adj_tile.transfer = tile.transfer
            tile.transfer = None
            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = adj_tile
            tile_placed = False

            while not tile_placed:
                if 'N' in tile.next and 'N' not in tile.caps:
                    if tile.tile_to_N == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "S" in tile_to_place.next:
                            tile_to_place.next.remove("S")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["S"]
                        tile_to_place.tile_to_S = tile
                        tile.tile_to_N = tile_to_place

                        tile.N = 'N'
                        tile_to_place.S = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('N')

                        if tile.previous == None: tile.S = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y + 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'E' in tile.next and 'E' not in tile.caps:
                    if tile.tile_to_E == None:
                        # Place the tile
                        tile_to_place = tile.transfer

                        if "W" in tile_to_place.next:
                            tile_to_place.next.remove("W")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["W"]
                        tile_to_place.tile_to_W = tile
                        tile.tile_to_E = tile_to_place

                        tile.E = 'N'
                        tile_to_place.W = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('E')

                        if tile.previous == None: tile.S = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x + 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")

                        tile = neighbor

                elif 'W' in tile.next and 'W' not in tile.caps:
                    if tile.tile_to_W == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "E" in tile_to_place.next:
                            tile_to_place.next.remove("E")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["E"]
                        tile_to_place.tile_to_E = tile
                        tile.tile_to_W = tile_to_place

                        tile.W = 'N'
                        tile_to_place.E = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('W')

                        if tile.previous == None: tile.S = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x - 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')

                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")

                        tile = neighbor

                elif 'S' in tile.next and 'S' not in tile.caps:
                    if tile.tile_to_S == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "N" in tile_to_place.next:
                            tile_to_place.next.remove("N")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["N"]
                        tile_to_place.tile_to_N = tile
                        tile.tile_to_S = tile_to_place

                        tile.S = 'N'
                        tile_to_place.N = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('S')

                        if tile.previous == None: tile.S = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y - 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')

                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")

                        tile = neighbor

                elif 'U' in tile.next and 'U' not in tile.caps:
                    if tile.tile_to_U == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "D" in tile_to_place.next:
                            tile_to_place.next.remove("D")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["D"]
                        tile_to_place.tile_to_D = tile
                        tile.tile_to_U = tile_to_place

                        tile.U = 'N'
                        tile_to_place.D = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('U')

                        if tile.previous == None: tile.S = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y 
                        tile_to_place.z = tile.z + 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'U')
                        
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.D
                        neighbor.D = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")

                        tile = neighbor

                elif 'D' in tile.next and 'D' not in tile.caps:
                    if tile.tile_to_D == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "U" in tile_to_place.next:
                            tile_to_place.next.remove("U")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["U"]
                        tile_to_place.tile_to_U = tile
                        tile.tile_to_D = tile_to_place

                        tile.D = 'N'
                        tile_to_place.U = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('D')

                        if tile.previous == None: tile.S = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z - 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'D')

                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.U
                        neighbor.U = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")

                        tile = neighbor

        breadcrumb_direction = breadcrumb_trail(tile)
        prev_tile = retrieve_tile(tile, breadcrumb_direction)

        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)

        tile.transfer = None

        if breadcrumb_direction == 'N': 
            tile.N = 'M'
        if breadcrumb_direction == 'E': 
            tile.E = 'M'
        if breadcrumb_direction == 'W': 
            tile.W = 'M'
        if breadcrumb_direction == 'S': 
            tile.S = 'M'
        if breadcrumb_direction == 'U': 
            tile.U = 'M'
        if breadcrumb_direction == 'D': 
            tile.D = 'M'

        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
        record_transition_snapshots(before_a, before_b, after_a, after_b, "Retrace breadcrumb trail")

        if len(tile.caps) == num_dirs(tile) and tile.key_tile_S == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                before_a, before_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                after_a, after_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
                record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                while len(t) > 0:
                    ct = t.pop()

                    # To store the last transition that occurs for ct
                    # after_b = None

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)
                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)
                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)
                                    after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)
                                    after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                    # before_a = _tile_snapshot(ct)
                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None
                    # after_a = _tile_snapshot(ct)
                    # record_transition_snapshots(before_a, after_b, after_a, after_b, "Finding pseudo seed")

                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)
                                ct.key_tile_N = '*'
                                ct.key_tile_E = '*'
                                ct.key_tile_W = '*'
                                ct.key_tile_S = '*'
                                ct.key_tile_U = '*'
                                ct.key_tile_D = '*'
                                if ct.copy_direction == 'r?': ct.copy_direction = 'r'

                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Propogating reset signal")

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)
                                ct.key_tile_N = '*'
                                ct.key_tile_E = '*'
                                ct.key_tile_W = '*'
                                ct.key_tile_S = '*'
                                ct.key_tile_U = '*'
                                ct.key_tile_D = '*'
                                if ct.copy_direction == 'r?': ct.copy_direction = 'r'

                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Propogating reset signal")

        while prev_tile.status != 'W':
            breadcrumb_direction = breadcrumb_trail(tile)

            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)

            if breadcrumb_direction == 'N':
                tile.N = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'E':
                tile.E = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'W':
                tile.W = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'S':
                tile.S = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'U':
                tile.U = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'D':
                tile.D = tile.temp
                tile.temp = None

            # Handle caps
            if move_caps(tile):
                prev_tile.caps.append(opp(breadcrumb_direction))
                tile.caps = []

            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Retracing breadcrumb trail")

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_S == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:

                before_a, before_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                after_a, after_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
                record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                while len(t) > 0:
                    ct = t.pop()

                    # To store the last transition that occurs for ct
                    # after_b = None

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)
                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)
                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)
                                    after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)
                                    after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                    # before_a = _tile_snapshot(ct)
                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None
                    # after_a = _tile_snapshot(ct)
                    # record_transition_snapshots(before_a, after_b, after_a, after_b, "Finding pseudo seed")

                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)
                                ct.key_tile_N = '*'
                                ct.key_tile_E = '*'
                                ct.key_tile_W = '*'
                                ct.key_tile_S = '*'
                                ct.key_tile_U = '*'
                                ct.key_tile_D = '*'
                                if ct.copy_direction == 'r?': ct.copy_direction = 'r'

                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Propogating reset signal")

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)
                                ct.key_tile_N = '*'
                                ct.key_tile_E = '*'
                                ct.key_tile_W = '*'
                                ct.key_tile_S = '*'
                                ct.key_tile_U = '*'
                                ct.key_tile_D = '*'
                                if ct.copy_direction == 'r?': ct.copy_direction = 'r'

                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Propogating reset signal")

            breadcrumb_direction = breadcrumb_trail(prev_tile)

            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
            if breadcrumb_direction == 'N':
                prev_tile.N = 'M'
            if breadcrumb_direction == 'E':
                prev_tile.E = 'M'
            if breadcrumb_direction == 'W':
                prev_tile.W = 'M'
            if breadcrumb_direction == 'S':
                prev_tile.S = 'M'
            if breadcrumb_direction == 'U':
                prev_tile.U = 'M'
            if breadcrumb_direction == 'D':
                prev_tile.D = 'M'

            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Retracing breadcrumb signal")

            tile = prev_tile
            prev_tile = retrieve_tile(tile, breadcrumb_direction)

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_S == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:

                before_a, before_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                after_a, after_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
                record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                while len(t) > 0:
                    ct = t.pop()

                    # To store the last transition that occurs for ct
                    # after_b = None

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)
                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)
                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)
                                    after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)
                                    after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                    record_transition_snapshots(before_a, before_b, after_a, after_b, "Finding pseudo seed")

                    # before_a = _tile_snapshot(ct)
                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None
                    # after_a = _tile_snapshot(ct)
                    # record_transition_snapshots(before_a, after_b, after_a, after_b, "Finding pseudo seed")

                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)
                                ct.key_tile_N = '*'
                                ct.key_tile_E = '*'
                                ct.key_tile_W = '*'
                                ct.key_tile_S = '*'
                                ct.key_tile_U = '*'
                                ct.key_tile_D = '*'
                                if ct.copy_direction == 'r?': ct.copy_direction = 'r'

                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Propogating reset signal")

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                before_a, before_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)
                                ct.key_tile_N = '*'
                                ct.key_tile_E = '*'
                                ct.key_tile_W = '*'
                                ct.key_tile_S = '*'
                                ct.key_tile_U = '*'
                                ct.key_tile_D = '*'
                                if ct.copy_direction == 'r?': ct.copy_direction = 'r'

                                after_a, after_b = _tile_snapshot(ct), _tile_snapshot(adj_tile)
                                record_transition_snapshots(before_a, before_b, after_a, after_b, "Propogating reset signal")

        breadcrumb_direction = breadcrumb_trail(tile)

        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
        if breadcrumb_direction == 'N':
            tile.N = 'N'
        if breadcrumb_direction == 'E':
            tile.E = 'N'
        if breadcrumb_direction == 'W':
            tile.W = 'N'
        if breadcrumb_direction == 'S':
            tile.S = 'N'
        if breadcrumb_direction == 'U':
            tile.U = 'N'
        if breadcrumb_direction == 'D':
            tile.D = 'N'

        prev_tile.status = 'F'
        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(prev_tile)
        record_transition_snapshots(before_a, before_b, after_a, after_b, "Marking tile as placed")

    # East
    if d == "E":
        while tile.key_tile_E != None:
            neighbor = retrieve_tile(tile, tile.key_tile_E[0])

            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

            neighbor.transfer = tile.transfer
            tile.transfer = None

            if tile.key_tile_E[0] == "N": 
                neighbor.temp = neighbor.S
                neighbor.S = "W"
            if tile.key_tile_E[0] == "E": 
                neighbor.temp = neighbor.W
                neighbor.W = "W"
            if tile.key_tile_E[0] == "W": 
                neighbor.temp = neighbor.E
                neighbor.E = "W"
            if tile.key_tile_E[0] == "S":
                neighbor.temp = neighbor.N 
                neighbor.N = "W"
            if tile.key_tile_E[0] == "U":
                neighbor.temp = neighbor.D 
                neighbor.D = "W"
            if tile.key_tile_E[0] == "D":
                neighbor.temp = neighbor.U 
                neighbor.U = "W"

            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = neighbor
        
        if tile.tile_to_E == None:

            tile_to_place = tile.transfer
            if "W" in tile_to_place.next:
                tile_to_place.next.remove("W")
            if len(tile_to_place.next) == 0: tile_to_place.next = None 
            # tile_to_place.previous = ["W"]
            tile_to_place.tile_to_W = tile
            tile.tile_to_E = tile_to_place

            tile.E, tile_to_place.W = None, 'N'

            tile.wall, tile_to_place.wall = True, True

            if tile.key_tile_W[0] == 'N': tile.N = 'M'
            if tile.key_tile_W[0] == 'E': tile.E = 'M'
            if tile.key_tile_W[0] == 'W': tile.W = 'M'
            if tile.key_tile_W[0] == 'S': tile.S = 'M'
            if tile.key_tile_W[0] == 'U': tile.U = 'M'
            if tile.key_tile_W[0] == 'D': tile.D = 'M'

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['W']
            if tile.new_n == None: tile.new_n = ['E']
            else: tile.new_n.append('E')

            tile_to_place.x = tile.x + 1
            tile_to_place.y = tile.y
            tile_to_place.z = tile.z
            tile_to_place.set_id()
            record_tile_placement(tile_to_place, tile)
        
        else:
            adj_tile = tile.tile_to_E
            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            adj_tile.W = 'W'
            adj_tile.transfer = tile.transfer
            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = adj_tile
            tile_placed = False


            while not tile_placed:

                if 'N' in tile.next and 'N' not in tile.caps:
                    if tile.tile_to_N == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "S" in tile_to_place.next:
                            tile_to_place.next.remove("S")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["S"]
                        tile_to_place.tile_to_S = tile
                        tile.tile_to_N = tile_to_place

                        tile.N = 'N'
                        tile_to_place.S = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('N')

                        if tile.previous == None: tile.W = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y + 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'E' in tile.next and 'E' not in tile.caps:
                    if tile.tile_to_E == None:
                        # Place the tile
                        tile_to_place = tile.transfer

                        if "W" in tile_to_place.next:
                            tile_to_place.next.remove("W")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["W"]
                        tile_to_place.tile_to_W = tile
                        tile.tile_to_E = tile_to_place

                        tile.E = 'N'
                        tile_to_place.W = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('E')
                            
                        if tile.previous == None: tile.W = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x + 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'W' in tile.next and 'W' not in tile.caps:
                    if tile.tile_to_W == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "E" in tile_to_place.next:
                            tile_to_place.next.remove("E")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["E"]
                        tile_to_place.tile_to_E = tile
                        tile.tile_to_W = tile_to_place

                        tile.W = 'N'
                        tile_to_place.E = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False
                        
                        if tile_to_place.terminal: 
                            tile.caps.append('W')
                            
                        if tile.previous == None: tile.W = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x - 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'S' in tile.next and 'S' not in tile.caps:
                    if tile.tile_to_S == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "N" in tile_to_place.next:
                            tile_to_place.next.remove("N")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["N"]
                        tile_to_place.tile_to_N = tile
                        tile.tile_to_S = tile_to_place

                        tile.S = 'N'
                        tile_to_place.N = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('S')
                            
                        if tile.previous == None: tile.W = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y - 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor
                
                elif 'U' in tile.next and 'U' not in tile.caps:
                    if tile.tile_to_U == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "D" in tile_to_place.next:
                            tile_to_place.next.remove("D")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["D"]
                        tile_to_place.tile_to_D = tile
                        tile.tile_to_U = tile_to_place

                        tile.U = 'N'
                        tile_to_place.D = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('U')
                            
                        if tile.previous == None: tile.W = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z + 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'U')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.D
                        neighbor.D = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'D' in tile.next and 'D' not in tile.caps:
                    if tile.tile_to_D == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "U" in tile_to_place.next:
                            tile_to_place.next.remove("U")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["U"]
                        tile_to_place.tile_to_U = tile
                        tile.tile_to_D = tile_to_place

                        tile.D = 'N'
                        tile_to_place.U = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('D')
                            
                        if tile.previous == None: tile.W = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z - 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'D')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.U
                        neighbor.U = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

        tile.transfer = None
        breadcrumb_direction = breadcrumb_trail(tile)
        if breadcrumb_direction == 'N': 
            tile.N = 'M'
        if breadcrumb_direction == 'E': 
            tile.E = 'M'
        if breadcrumb_direction == 'W': 
            tile.W = 'M'
        if breadcrumb_direction == 'S': 
            tile.S = 'M'
        if breadcrumb_direction == 'U': 
            tile.U = 'M'
        if breadcrumb_direction == 'D': 
            tile.D = 'M'

        prev_tile = retrieve_tile(tile, breadcrumb_direction)

        if len(tile.caps) == num_dirs(tile) and tile.key_tile_W == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        while prev_tile.status != 'W':
            breadcrumb_direction = breadcrumb_trail(tile)

            if breadcrumb_direction == 'N':
                tile.N = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'E':
                tile.E = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'W':
                tile.W = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'S':
                tile.S = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'U':
                tile.U = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'D':
                tile.D = tile.temp
                tile.temp = None

            # Handle caps
            if move_caps(tile):
                prev_tile.caps.append(opp(breadcrumb_direction))
                tile.caps = []

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_W == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

            breadcrumb_direction = breadcrumb_trail(prev_tile)

            if breadcrumb_direction == 'N':
                prev_tile.N = 'M'
            if breadcrumb_direction == 'E':
                prev_tile.E = 'M'
            if breadcrumb_direction == 'W':
                prev_tile.W = 'M'
            if breadcrumb_direction == 'S':
                prev_tile.S = 'M'
            if breadcrumb_direction == 'U':
                prev_tile.U = 'M'
            if breadcrumb_direction == 'D':
                prev_tile.D = 'M'

            tile = prev_tile
            prev_tile = retrieve_tile(tile, breadcrumb_direction)

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_W == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        breadcrumb_direction = breadcrumb_trail(tile)

        if breadcrumb_direction == 'N':
            tile.N = 'N'
        if breadcrumb_direction == 'E':
            tile.E = 'N'
        if breadcrumb_direction == 'W':
            tile.W = 'N'
        if breadcrumb_direction == 'S':
            tile.S = 'N'
        if breadcrumb_direction == 'U':
            tile.U = 'N'
        if breadcrumb_direction == 'D':
            tile.D = 'N'

        prev_tile.status = 'F'


    # West
    if d == "W":
        while tile.key_tile_W != None:
            neighbor = retrieve_tile(tile, tile.key_tile_W[0])

            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

            neighbor.transfer = tile.transfer
            tile.transfer = None

            if tile.key_tile_W[0] == "N": 
                neighbor.temp = neighbor.S
                neighbor.S = "W"
            if tile.key_tile_W[0] == "E": 
                neighbor.temp = neighbor.W
                neighbor.W = "W"
            if tile.key_tile_W[0] == "W": 
                neighbor.temp = neighbor.E
                neighbor.E = "W"
            if tile.key_tile_W[0] == "S":
                neighbor.temp = neighbor.N 
                neighbor.N = "W"
            if tile.key_tile_W[0] == "U":
                neighbor.temp = neighbor.D 
                neighbor.D = "W"
            if tile.key_tile_W[0] == "D":
                neighbor.temp = neighbor.U 
                neighbor.U = "W"

            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = neighbor

        if tile.tile_to_W == None:
            tile_to_place = tile.transfer
            if "E" in tile_to_place.next:
                tile_to_place.next.remove("E")
            if len(tile_to_place.next) == 0: tile_to_place.next = None 
            tile.tile_to_W = tile_to_place
            tile_to_place.tile_to_E = tile

            tile.W, tile_to_place.E = None, 'N'

            tile.wall, tile_to_place.wall = True, True

            if tile.key_tile_E[0] == 'N': tile.N = 'M'
            if tile.key_tile_E[0] == 'E': tile.E = 'M'
            if tile.key_tile_E[0] == 'W': tile.W = 'M'
            if tile.key_tile_E[0] == 'S': tile.S = 'M'
            if tile.key_tile_E[0] == 'U': tile.U = 'M'
            if tile.key_tile_E[0] == 'D': tile.D = 'M'

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['E']
            if tile.new_n == None: tile.new_n = ['W']
            else: tile.new_n.append('W')

            tile_to_place.x = tile.x - 1
            tile_to_place.y = tile.y
            tile_to_place.z = tile.z
            tile_to_place.set_id()
            record_tile_placement(tile_to_place, tile)

        else: 
            adj_tile = tile.tile_to_W
            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            adj_tile.E = 'W'
            adj_tile.transfer = tile.transfer
            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = adj_tile
            tile_placed = False

            while not tile_placed:

                if 'N' in tile.next and 'N' not in tile.caps:
                    if tile.tile_to_N == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "S" in tile_to_place.next:
                            tile_to_place.next.remove("S")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["S"]
                        tile_to_place.tile_to_S = tile
                        tile.tile_to_N = tile_to_place

                        tile.N = 'N'
                        tile_to_place.S = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('N')
                            
                        if tile.previous == None: tile.E = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y + 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'E' in tile.next and 'E' not in tile.caps:
                    if tile.tile_to_E == None:
                        # Place the tile
                        tile_to_place = tile.transfer

                        if "W" in tile_to_place.next:
                            tile_to_place.next.remove("W")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["W"]
                        tile_to_place.tile_to_W = tile
                        tile.tile_to_E = tile_to_place

                        tile.E = 'N'
                        tile_to_place.W = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('E')
                            
                        if tile.previous == None: tile.E = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x + 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'W' in tile.next and 'W' not in tile.caps:
                    if tile.tile_to_W == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "E" in tile_to_place.next:
                            tile_to_place.next.remove("E")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["E"]
                        tile_to_place.tile_to_E = tile
                        tile.tile_to_W = tile_to_place

                        tile.W = 'N'
                        tile_to_place.E = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('W')
                            
                        if tile.previous == None: tile.E = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x - 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'S' in tile.next and 'S' not in tile.caps:
                    if tile.tile_to_S == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "N" in tile_to_place.next:
                            tile_to_place.next.remove("N")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["N"]
                        tile_to_place.tile_to_N = tile
                        tile.tile_to_S = tile_to_place

                        tile.S = 'N'
                        tile_to_place.N = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('S')
                            
                        if tile.previous == None: tile.E = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y - 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor
                        
                elif 'U' in tile.next and 'U' not in tile.caps:
                    if tile.tile_to_U == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "D" in tile_to_place.next:
                            tile_to_place.next.remove("D")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["D"]
                        tile_to_place.tile_to_D = tile
                        tile.tile_to_U = tile_to_place

                        tile.U = 'N'
                        tile_to_place.D = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('U')
                            
                        if tile.previous == None: tile.E = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z + 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'U')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.D
                        neighbor.D = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'D' in tile.next and 'D' not in tile.caps:
                    if tile.tile_to_D == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "U" in tile_to_place.next:
                            tile_to_place.next.remove("U")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["U"]
                        tile_to_place.tile_to_U = tile
                        tile.tile_to_D = tile_to_place

                        tile.D = 'N'
                        tile_to_place.U = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('D')
                            
                        if tile.previous == None: tile.E = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z - 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'D')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.U
                        neighbor.U = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

        tile.transfer = None
        breadcrumb_direction = breadcrumb_trail(tile)
        if breadcrumb_direction == 'N': 
            tile.N = 'M'
        if breadcrumb_direction == 'E': 
            tile.E = 'M'
        if breadcrumb_direction == 'W': 
            tile.W = 'M'
        if breadcrumb_direction == 'S': 
            tile.S = 'M'
        if breadcrumb_direction == 'U': 
            tile.U = 'M'
        if breadcrumb_direction == 'D': 
            tile.D = 'M'

        prev_tile = retrieve_tile(tile, breadcrumb_direction)

        if len(tile.caps) == num_dirs(tile) and tile.key_tile_E == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        while prev_tile.status != 'W':
            
            breadcrumb_direction = breadcrumb_trail(tile)

            if breadcrumb_direction == 'N':
                tile.N = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'E':
                tile.E = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'W':
                tile.W = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'S':
                tile.S = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'U':
                tile.U = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'D':
                tile.D = tile.temp
                tile.temp = None

            # Handle caps
            if move_caps(tile):
                prev_tile.caps.append(opp(breadcrumb_direction))
                tile.caps = []

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_E == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

            breadcrumb_direction = breadcrumb_trail(prev_tile)

            if breadcrumb_direction == 'N':
                prev_tile.N = 'M'
            if breadcrumb_direction == 'E':
                prev_tile.E = 'M'
            if breadcrumb_direction == 'W':
                prev_tile.W = 'M'
            if breadcrumb_direction == 'S':
                prev_tile.S = 'M'
            if breadcrumb_direction == 'U':
                prev_tile.U = 'M'
            if breadcrumb_direction == 'D':
                prev_tile.D = 'M'
            
            tile = prev_tile
            prev_tile = retrieve_tile(tile, breadcrumb_direction)

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_E == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        breadcrumb_direction = breadcrumb_trail(tile)

        if breadcrumb_direction == 'N':
            tile.N = 'N'
        if breadcrumb_direction == 'E':
            tile.E = 'N'
        if breadcrumb_direction == 'W':
            tile.W = 'N'
        if breadcrumb_direction == 'S':
            tile.S = 'N'
        if breadcrumb_direction == 'U':
            tile.U = 'N'
        if breadcrumb_direction == 'D':
            tile.D = 'N'

        prev_tile.status = 'F'

    # South
    if d == "S":
        while tile.key_tile_S != None:
            neighbor = retrieve_tile(tile, tile.key_tile_S[0])

            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

            neighbor.transfer = tile.transfer
            tile.transfer = None

            if tile.key_tile_S[0] == "N": 
                neighbor.temp = neighbor.S
                neighbor.S = "W"
            if tile.key_tile_S[0] == "E": 
                neighbor.temp = neighbor.W
                neighbor.W = "W"
            if tile.key_tile_S[0] == "W": 
                neighbor.temp = neighbor.E
                neighbor.E = "W"
            if tile.key_tile_S[0] == "S": 
                neighbor.temp = neighbor.N
                neighbor.N = "W"
            if tile.key_tile_S[0] == "U": 
                neighbor.temp = neighbor.D
                neighbor.D = "W"
            if tile.key_tile_S[0] == "D": 
                neighbor.temp = neighbor.U
                neighbor.U = "W"

            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = neighbor

        if tile.tile_to_S == None:
            tile_to_place = tile.transfer
            if "N" in tile_to_place.next:
                tile_to_place.next.remove("N")
            if len(tile_to_place.next) == 0: tile_to_place.next = None 
            # tile_to_place.previous = ["N"]
            tile.tile_to_S = tile_to_place
            tile_to_place.tile_to_N = tile
            tile.S, tile_to_place.N = None, 'N'

            tile.wall, tile_to_place.wall = True, True

            if tile.key_tile_N[0] == 'N': tile.N = 'M'
            if tile.key_tile_N[0] == 'E': tile.E = 'M'
            if tile.key_tile_N[0] == 'W': tile.W = 'M'
            if tile.key_tile_N[0] == 'S': tile.S = 'M'
            if tile.key_tile_N[0] == 'U': tile.U = 'M'
            if tile.key_tile_N[0] == 'D': tile.D = 'M'

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['N']
            if tile.new_n == None: tile.new_n = ['S']
            else: tile.new_n.append('S')

            tile_to_place.x = tile.x
            tile_to_place.y = tile.y - 1
            tile_to_place.z = tile.z
            tile_to_place.set_id()
            record_tile_placement(tile_to_place, tile)
            # tile.new_p = copy.copy(tile.previous)

        else: 
            adj_tile = tile.tile_to_S
            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            adj_tile.N = 'W'
            adj_tile.transfer = tile.transfer
            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = adj_tile
            tile_placed = False

            while not tile_placed:

                if 'N' in tile.next and 'N' not in tile.caps:
                    if tile.tile_to_N == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "S" in tile_to_place.next:
                            tile_to_place.next.remove("S")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["S"]
                        tile_to_place.tile_to_S = tile
                        tile.tile_to_N = tile_to_place

                        tile.N = 'N'
                        tile_to_place.S = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('N')
                            
                        if tile.previous == None: tile.N = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y + 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'E' in tile.next and 'E' not in tile.caps:
                    if tile.tile_to_E == None:
                        # Place the tile
                        tile_to_place = tile.transfer

                        if "W" in tile_to_place.next:
                            tile_to_place.next.remove("W")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["W"]
                        tile_to_place.tile_to_W = tile
                        tile.tile_to_E = tile_to_place

                        tile.E = 'N'
                        tile_to_place.W = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('E')
                            
                        if tile.previous == None: tile.N = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x + 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'W' in tile.next and 'W' not in tile.caps:
                    if tile.tile_to_W == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "E" in tile_to_place.next:
                            tile_to_place.next.remove("E")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["E"]
                        tile_to_place.tile_to_E = tile
                        tile.tile_to_W = tile_to_place

                        tile.W = 'N'
                        tile_to_place.E = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False
                        
                        if tile_to_place.terminal: 
                            tile.caps.append('W')
                            
                        if tile.previous == None: tile.N = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x - 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'S' in tile.next and 'S' not in tile.caps:
                    if tile.tile_to_S == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "N" in tile_to_place.next:
                            tile_to_place.next.remove("N")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["N"]
                        tile_to_place.tile_to_N = tile
                        tile.tile_to_S = tile_to_place

                        tile.S = 'N'
                        tile_to_place.N = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('S')
                            
                        if tile.previous == None: tile.N = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y - 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'U' in tile.next and 'U' not in tile.caps:
                    if tile.tile_to_U == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "D" in tile_to_place.next:
                            tile_to_place.next.remove("D")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["D"]
                        tile_to_place.tile_to_D = tile
                        tile.tile_to_U = tile_to_place

                        tile.U = 'N'
                        tile_to_place.D = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('U')
                            
                        if tile.previous == None: tile.N = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z + 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'U')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.D
                        neighbor.D = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'D' in tile.next and 'D' not in tile.caps:
                    if tile.tile_to_D == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "U" in tile_to_place.next:
                            tile_to_place.next.remove("U")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["U"]
                        tile_to_place.tile_to_U = tile
                        tile.tile_to_D = tile_to_place

                        tile.D = 'N'
                        tile_to_place.U = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('D')
                            
                        if tile.previous == None: tile.N = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z - 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'D')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.U
                        neighbor.U = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

        tile.transfer = None
        breadcrumb_direction = breadcrumb_trail(tile)
        if breadcrumb_direction == 'N': 
            tile.N = 'M'
        if breadcrumb_direction == 'E': 
            tile.E = 'M'
        if breadcrumb_direction == 'W': 
            tile.W = 'M'
        if breadcrumb_direction == 'S': 
            tile.S = 'M'
        if breadcrumb_direction == 'U': 
            tile.U = 'M'
        if breadcrumb_direction == 'D': 
            tile.D = 'M'

        prev_tile = retrieve_tile(tile, breadcrumb_direction)

        if len(tile.caps) == num_dirs(tile) and tile.key_tile_N == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                # Pass reset through subassembly
                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        while prev_tile.status != 'W':
            breadcrumb_direction = breadcrumb_trail(tile)

            if breadcrumb_direction == 'N':
                tile.N = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'E':
                tile.E = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'W':
                tile.W = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'S':
                tile.S = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'U':
                tile.U = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'D':
                tile.D = tile.temp
                tile.temp = None

            # Handle caps
            if move_caps(tile):
                prev_tile.caps.append(opp(breadcrumb_direction))
                tile.caps = []

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_N == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                # Pass reset through subassembly
                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

            breadcrumb_direction = breadcrumb_trail(prev_tile)

            if breadcrumb_direction == 'N':
                prev_tile.N = 'M'
            if breadcrumb_direction == 'E':
                prev_tile.E = 'M'
            if breadcrumb_direction == 'W':
                prev_tile.W = 'M'
            if breadcrumb_direction == 'S':
                prev_tile.S = 'M'
            if breadcrumb_direction == 'U':
                prev_tile.U = 'M'
            if breadcrumb_direction == 'D':
                prev_tile.D = 'M'

            tile = prev_tile
            prev_tile = retrieve_tile(tile, breadcrumb_direction)

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_N == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                # Pass reset through subassembly
                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        breadcrumb_direction = breadcrumb_trail(tile)

        if breadcrumb_direction == 'N':
            tile.N = 'N'
        if breadcrumb_direction == 'E':
            tile.E = 'N'
        if breadcrumb_direction == 'W':
            tile.W = 'N'
        if breadcrumb_direction == 'S':
            tile.S = 'N'
        if breadcrumb_direction == 'U':
            tile.U = 'N'
        if breadcrumb_direction == 'D':
            tile.D = 'N'

        prev_tile.status = 'F'

    # Up
    if d == "U":
        while tile.key_tile_U != None:
            neighbor = retrieve_tile(tile, tile.key_tile_U[0])

            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

            neighbor.transfer = tile.transfer
            tile.transfer = None

            if tile.key_tile_U[0] == "N": 
                neighbor.temp = neighbor.S
                neighbor.S = "W"
            if tile.key_tile_U[0] == "E": 
                neighbor.temp = neighbor.W
                neighbor.W = "W"
            if tile.key_tile_U[0] == "W": 
                neighbor.temp = neighbor.E
                neighbor.E = "W"
            if tile.key_tile_U[0] == "S": 
                neighbor.temp = neighbor.N
                neighbor.N = "W"
            if tile.key_tile_U[0] == "U": 
                neighbor.temp = neighbor.D
                neighbor.D = "W"
            if tile.key_tile_U[0] == "D": 
                neighbor.temp = neighbor.U
                neighbor.U = "W"

            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = neighbor

        if tile.tile_to_U == None:
            tile_to_place = tile.transfer
            if "D" in tile_to_place.next:
                tile_to_place.next.remove("D")
            if len(tile_to_place.next) == 0: tile_to_place.next = None 
        
            tile.tile_to_U = tile_to_place
            tile_to_place.tile_to_D = tile
            tile.U, tile_to_place.D = None, 'N'

            tile.wall, tile_to_place.wall = True, True

            if tile.key_tile_D[0] == 'N': tile.N = 'M'
            if tile.key_tile_D[0] == 'E': tile.E = 'M'
            if tile.key_tile_D[0] == 'W': tile.W = 'M'
            if tile.key_tile_D[0] == 'S': tile.S = 'M'
            if tile.key_tile_D[0] == 'U': tile.U = 'M'
            if tile.key_tile_D[0] == 'D': tile.D = 'M'

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['D']
            if tile.new_n == None: tile.new_n = ['U']
            else: tile.new_n.append('U')

            tile_to_place.x = tile.x
            tile_to_place.y = tile.y
            tile_to_place.z = tile.z + 1
            tile_to_place.set_id()
            record_tile_placement(tile_to_place, tile)

        else: 
            adj_tile = tile.tile_to_U
            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            adj_tile.D = 'W'
            adj_tile.transfer = tile.transfer
            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = adj_tile
            tile_placed = False

            while not tile_placed:

                if 'N' in tile.next and 'N' not in tile.caps:
                    if tile.tile_to_N == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "S" in tile_to_place.next:
                            tile_to_place.next.remove("S")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["S"]
                        tile_to_place.tile_to_S = tile
                        tile.tile_to_N = tile_to_place

                        tile.N = 'N'
                        tile_to_place.S = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('N')
                            
                        if tile.previous == None: tile.D = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y + 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'E' in tile.next and 'E' not in tile.caps:
                    if tile.tile_to_E == None:
                        # Place the tile
                        tile_to_place = tile.transfer

                        if "W" in tile_to_place.next:
                            tile_to_place.next.remove("W")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["W"]
                        tile_to_place.tile_to_W = tile
                        tile.tile_to_E = tile_to_place

                        tile.E = 'N'
                        tile_to_place.W = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('E')
                            
                        if tile.previous == None: tile.D = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x + 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'W' in tile.next and 'W' not in tile.caps:
                    if tile.tile_to_W == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "E" in tile_to_place.next:
                            tile_to_place.next.remove("E")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["E"]
                        tile_to_place.tile_to_E = tile
                        tile.tile_to_W = tile_to_place

                        tile.W = 'N'
                        tile_to_place.E = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False
                        
                        if tile_to_place.terminal: 
                            tile.caps.append('W')
                            
                        if tile.previous == None: tile.D = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x - 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'S' in tile.next and 'S' not in tile.caps:
                    if tile.tile_to_S == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "N" in tile_to_place.next:
                            tile_to_place.next.remove("N")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["N"]
                        tile_to_place.tile_to_N = tile
                        tile.tile_to_S = tile_to_place

                        tile.S = 'N'
                        tile_to_place.N = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('S')
                            
                        if tile.previous == None: tile.D = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y - 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'U' in tile.next and 'U' not in tile.caps:
                    if tile.tile_to_U == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "D" in tile_to_place.next:
                            tile_to_place.next.remove("D")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["D"]
                        tile_to_place.tile_to_D = tile
                        tile.tile_to_U = tile_to_place

                        tile.U = 'N'
                        tile_to_place.D = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('U')
                            
                        if tile.previous == None: tile.D = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z + 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'U')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.D
                        neighbor.D = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'D' in tile.next and 'D' not in tile.caps:
                    if tile.tile_to_D == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "U" in tile_to_place.next:
                            tile_to_place.next.remove("U")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["U"]
                        tile_to_place.tile_to_U = tile
                        tile.tile_to_D = tile_to_place

                        tile.D = 'N'
                        tile_to_place.U = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('D')
                            
                        if tile.previous == None: tile.D = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z - 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'D')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.U
                        neighbor.U = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

        tile.transfer = None
        breadcrumb_direction = breadcrumb_trail(tile)
        if breadcrumb_direction == 'N': 
            tile.N = 'M'
        if breadcrumb_direction == 'E': 
            tile.E = 'M'
        if breadcrumb_direction == 'W': 
            tile.W = 'M'
        if breadcrumb_direction == 'S': 
            tile.S = 'M'
        if breadcrumb_direction == 'U': 
            tile.U = 'M'
        if breadcrumb_direction == 'D': 
            tile.D = 'M'

        prev_tile = retrieve_tile(tile, breadcrumb_direction)

        if len(tile.caps) == num_dirs(tile) and tile.key_tile_D == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                # Pass reset through subassembly
                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        while prev_tile.status != 'W':
            breadcrumb_direction = breadcrumb_trail(tile)

            if breadcrumb_direction == 'N':
                tile.N = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'E':
                tile.E = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'W':
                tile.W = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'S':
                tile.S = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'U':
                tile.U = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'D':
                tile.D = tile.temp
                tile.temp = None

            # Handle caps
            if move_caps(tile):
                prev_tile.caps.append(opp(breadcrumb_direction))
                tile.caps = []

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_D == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                # Pass reset through subassembly
                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

            breadcrumb_direction = breadcrumb_trail(prev_tile)

            if breadcrumb_direction == 'N':
                prev_tile.N = 'M'
            if breadcrumb_direction == 'E':
                prev_tile.E = 'M'
            if breadcrumb_direction == 'W':
                prev_tile.W = 'M'
            if breadcrumb_direction == 'S':
                prev_tile.S = 'M'
            if breadcrumb_direction == 'U':
                prev_tile.U = 'M'
            if breadcrumb_direction == 'D':
                prev_tile.D = 'M'

            tile = prev_tile
            prev_tile = retrieve_tile(tile, breadcrumb_direction)

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_D == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                # Pass reset through subassembly
                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        breadcrumb_direction = breadcrumb_trail(tile)

        if breadcrumb_direction == 'N':
            tile.N = 'N'
        if breadcrumb_direction == 'E':
            tile.E = 'N'
        if breadcrumb_direction == 'W':
            tile.W = 'N'
        if breadcrumb_direction == 'S':
            tile.S = 'N'
        if breadcrumb_direction == 'U':
            tile.U = 'N'
        if breadcrumb_direction == 'D':
            tile.D = 'N'

        prev_tile.status = 'F'

    # Down
    if d == "D":
        while tile.key_tile_D != None:
            neighbor = retrieve_tile(tile, tile.key_tile_D[0])

            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

            neighbor.transfer = tile.transfer
            tile.transfer = None

            if tile.key_tile_D[0] == "N": 
                neighbor.temp = neighbor.S
                neighbor.S = "W"
            if tile.key_tile_D[0] == "E": 
                neighbor.temp = neighbor.W
                neighbor.W = "W"
            if tile.key_tile_D[0] == "W": 
                neighbor.temp = neighbor.E
                neighbor.E = "W"
            if tile.key_tile_D[0] == "S": 
                neighbor.temp = neighbor.N
                neighbor.N = "W"
            if tile.key_tile_D[0] == "U": 
                neighbor.temp = neighbor.D
                neighbor.D = "W"
            if tile.key_tile_D[0] == "D": 
                neighbor.temp = neighbor.U
                neighbor.U = "W"

            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = neighbor

        if tile.tile_to_D == None:
            tile_to_place = tile.transfer
            if "U" in tile_to_place.next:
                tile_to_place.next.remove("U")
            if len(tile_to_place.next) == 0: tile_to_place.next = None 
        
            tile.tile_to_D = tile_to_place
            tile_to_place.tile_to_U = tile
            tile.D, tile_to_place.U = None, 'N'

            tile.wall, tile_to_place.wall = True, True

            if tile.key_tile_U[0] == 'N': tile.N = 'M'
            if tile.key_tile_U[0] == 'E': tile.E = 'M'
            if tile.key_tile_U[0] == 'W': tile.W = 'M'
            if tile.key_tile_U[0] == 'S': tile.S = 'M'
            if tile.key_tile_U[0] == 'U': tile.U = 'M'
            if tile.key_tile_U[0] == 'D': tile.D = 'M'

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['U']
            if tile.new_n == None: tile.new_n = ['D']
            else: tile.new_n.append('D')

            tile_to_place.x = tile.x
            tile_to_place.y = tile.y
            tile_to_place.z = tile.z - 1
            tile_to_place.set_id()
            record_tile_placement(tile_to_place, tile)

        else: 
            adj_tile = tile.tile_to_D
            before_a, before_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            adj_tile.U = 'W'
            adj_tile.transfer = tile.transfer
            after_a, after_b = _tile_snapshot(tile), _tile_snapshot(adj_tile)
            record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
            tile = adj_tile
            tile_placed = False

            while not tile_placed:

                if 'N' in tile.next and 'N' not in tile.caps:
                    if tile.tile_to_N == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "S" in tile_to_place.next:
                            tile_to_place.next.remove("S")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["S"]
                        tile_to_place.tile_to_S = tile
                        tile.tile_to_N = tile_to_place

                        tile.N = 'N'
                        tile_to_place.S = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('N')
                            
                        if tile.previous == None: tile.U = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y + 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'E' in tile.next and 'E' not in tile.caps:
                    if tile.tile_to_E == None:
                        # Place the tile
                        tile_to_place = tile.transfer

                        if "W" in tile_to_place.next:
                            tile_to_place.next.remove("W")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["W"]
                        tile_to_place.tile_to_W = tile
                        tile.tile_to_E = tile_to_place

                        tile.E = 'N'
                        tile_to_place.W = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('E')
                            
                        if tile.previous == None: tile.U = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x + 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'W' in tile.next and 'W' not in tile.caps:
                    if tile.tile_to_W == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "E" in tile_to_place.next:
                            tile_to_place.next.remove("E")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["E"]
                        tile_to_place.tile_to_E = tile
                        tile.tile_to_W = tile_to_place

                        tile.W = 'N'
                        tile_to_place.E = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False
                        
                        if tile_to_place.terminal: 
                            tile.caps.append('W')
                            
                        if tile.previous == None: tile.U = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x - 1
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'S' in tile.next and 'S' not in tile.caps:
                    if tile.tile_to_S == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "N" in tile_to_place.next:
                            tile_to_place.next.remove("N")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["N"]
                        tile_to_place.tile_to_N = tile
                        tile.tile_to_S = tile_to_place

                        tile.S = 'N'
                        tile_to_place.N = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('S')
                            
                        if tile.previous == None: tile.U = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y - 1
                        tile_to_place.z = tile.z
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'U' in tile.next and 'U' not in tile.caps:
                    if tile.tile_to_U == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "D" in tile_to_place.next:
                            tile_to_place.next.remove("D")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["D"]
                        tile_to_place.tile_to_D = tile
                        tile.tile_to_U = tile_to_place

                        tile.U = 'N'
                        tile_to_place.D = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('U')
                            
                        if tile.previous == None: tile.U = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z + 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'U')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.D
                        neighbor.D = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

                elif 'D' in tile.next and 'D' not in tile.caps:
                    if tile.tile_to_D == None:
                        # Place the tile
                        tile_to_place = tile.transfer
                        if "U" in tile_to_place.next:
                            tile_to_place.next.remove("U")
                        if len(tile_to_place.next) == 0: tile_to_place.next = None 
                        tile_to_place.previous = ["U"]
                        tile_to_place.tile_to_U = tile
                        tile.tile_to_D = tile_to_place

                        tile.D = 'N'
                        tile_to_place.U = 'N'

                        tile_placed = True

                        if tile_to_place.pseudo_seed: pseudo_seed = tile_to_place

                        # Handle caps
                        if tile_to_place.next == None: tile_to_place.terminal = True
                        else: tile_to_place.terminal = False

                        if tile_to_place.terminal: 
                            tile.caps.append('D')
                            
                        if tile.previous == None: tile.U = 'M'
                        elif tile.previous[0] == 'N': tile.N = 'M' 
                        elif tile.previous[0] == 'E': tile.E = 'M'
                        elif tile.previous[0] == 'W': tile.W = 'M'
                        elif tile.previous[0] == 'S': tile.S = 'M'
                        elif tile.previous[0] == 'U': tile.U = 'M'
                        elif tile.previous[0] == 'D': tile.D = 'M'

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                        tile_to_place.x = tile.x
                        tile_to_place.y = tile.y
                        tile_to_place.z = tile.z - 1
                        tile_to_place.set_id()
                        record_tile_placement(tile_to_place, tile)

                    else: 
                        neighbor = retrieve_tile(tile, 'D')
                        before_a, before_b = _tile_snapshot(tile), _tile_snapshot(neighbor)

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.U
                        neighbor.U = 'W'

                        after_a, after_b = _tile_snapshot(tile), _tile_snapshot(neighbor)
                        record_transition_snapshots(before_a, before_b, after_a, after_b, "Copying tile")
                        tile = neighbor

        tile.transfer = None
        breadcrumb_direction = breadcrumb_trail(tile)
        if breadcrumb_direction == 'N': 
            tile.N = 'M'
        if breadcrumb_direction == 'E': 
            tile.E = 'M'
        if breadcrumb_direction == 'W': 
            tile.W = 'M'
        if breadcrumb_direction == 'S': 
            tile.S = 'M'
        if breadcrumb_direction == 'U': 
            tile.U = 'M'
        if breadcrumb_direction == 'D': 
            tile.D = 'M'

        prev_tile = retrieve_tile(tile, breadcrumb_direction)

        if len(tile.caps) == num_dirs(tile) and tile.key_tile_U == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                # Pass reset through subassembly
                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        while prev_tile.status != 'W':
            breadcrumb_direction = breadcrumb_trail(tile)

            if breadcrumb_direction == 'N':
                tile.N = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'E':
                tile.E = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'W':
                tile.W = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'S':
                tile.S = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'U':
                tile.U = tile.temp
                tile.temp = None
            if breadcrumb_direction == 'D':
                tile.D = tile.temp
                tile.temp = None

            # Handle caps
            if move_caps(tile):
                prev_tile.caps.append(opp(breadcrumb_direction))
                tile.caps = []

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_U == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                # Pass reset through subassembly
                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

            breadcrumb_direction = breadcrumb_trail(prev_tile)

            if breadcrumb_direction == 'N':
                prev_tile.N = 'M'
            if breadcrumb_direction == 'E':
                prev_tile.E = 'M'
            if breadcrumb_direction == 'W':
                prev_tile.W = 'M'
            if breadcrumb_direction == 'S':
                prev_tile.S = 'M'
            if breadcrumb_direction == 'U':
                prev_tile.U = 'M'
            if breadcrumb_direction == 'D':
                prev_tile.D = 'M'

            tile = prev_tile
            prev_tile = retrieve_tile(tile, breadcrumb_direction)

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_U == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:
                # Find pseudo seed
                tile.copy_direction = '?'
                t = [tile]
                r_tile = None

                while len(t) > 0:
                    ct = t.pop()

                    if ct.copy_direction == '?':
                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None:
                                    adj_tile.copy_direction = '?' + opp(neighbor)
                                    t.append(adj_tile)

                    else: 
                        l = list(ct.copy_direction)
                        if ct.next != None: 
                            for neighbor in ct.next:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                if neighbor != l[1]: 
                                    adj_tile = retrieve_tile(ct, neighbor)
                                    if adj_tile != None:
                                        adj_tile.copy_direction = '?' + opp(neighbor)
                                        t.append(adj_tile)

                    if ct.pseudo_seed: 
                        if ct.terminal: 
                            ct.copy_direction = 'R'
                            r_tile = ct
                            hard_reset_tiles.append(ct)
                        else: ct.copy_direction = 'Y'
                    else: ct.copy_direction = None

                # Pass reset through subassembly
                if r_tile != None:
                    t = [r_tile]
                    while len(t) > 0:
                        ct = t.pop()

                        if ct.next != None: 
                            for neighbor in ct.next:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        if ct.previous != None: 
                            for neighbor in ct.previous:
                                adj_tile = retrieve_tile(ct, neighbor)
                                if adj_tile != None and adj_tile.copy_direction == None:
                                    adj_tile.copy_direction = 'r?'
                                    t.append(adj_tile)

                        ct.key_tile_N = '*'
                        ct.key_tile_E = '*'
                        ct.key_tile_W = '*'
                        ct.key_tile_S = '*'
                        ct.key_tile_U = '*'
                        ct.key_tile_D = '*'
                        if ct.copy_direction == 'r?': ct.copy_direction = 'r'

        breadcrumb_direction = breadcrumb_trail(tile)

        if breadcrumb_direction == 'N':
            tile.N = 'N'
        if breadcrumb_direction == 'E':
            tile.E = 'N'
        if breadcrumb_direction == 'W':
            tile.W = 'N'
        if breadcrumb_direction == 'S':
            tile.S = 'N'
        if breadcrumb_direction == 'U':
            tile.U = 'N'
        if breadcrumb_direction == 'D':
            tile.D = 'N'

        prev_tile.status = 'F'

    return pseudo_seed 

def copy_assembly(tile, d, cancel_callback=None): 
    _raise_if_cancelled(cancel_callback)
    pseudo_seed = None
    returned_pseudo_seed = None
    tile.copied = True

    if d == "N":
        pseudo_seed = tile.tile_to_N
        while tile.key_tile_S != None:
            _raise_if_cancelled(cancel_callback)
            tile = retrieve_tile(tile, tile.key_tile_S[0])
    if d == "E":
        pseudo_seed = tile.tile_to_E
        while tile.key_tile_W != None:
            _raise_if_cancelled(cancel_callback)
            tile = retrieve_tile(tile, tile.key_tile_W[0])
    if d == "W":
        pseudo_seed = tile.tile_to_W
        while tile.key_tile_E != None:
            _raise_if_cancelled(cancel_callback)
            tile = retrieve_tile(tile, tile.key_tile_E[0])
    if d == "S":
        pseudo_seed = tile.tile_to_S
        while tile.key_tile_N != None:
            _raise_if_cancelled(cancel_callback)
            tile = retrieve_tile(tile, tile.key_tile_N[0])
    if d == "U":
        pseudo_seed = tile.tile_to_U
        while tile.key_tile_D != None:
            _raise_if_cancelled(cancel_callback)
            tile = retrieve_tile(tile, tile.key_tile_D[0])
    if d == "D":
        pseudo_seed = tile.tile_to_D
        while tile.key_tile_U != None:
            _raise_if_cancelled(cancel_callback)
            tile = retrieve_tile(tile, tile.key_tile_U[0])

    starting_tile = tile
    starting_tile.first_tile = True
    while not is_assembly_finished(starting_tile):
        _raise_if_cancelled(cancel_callback)
        # copy tile
        is_pseudo_seed = copy_tile(tile, d, pseudo_seed)

        if is_pseudo_seed != None: 
            returned_pseudo_seed = is_pseudo_seed

        if num_dirs(tile) == 1 and not tile.original_seed and not tile.pseudo_seed and tile != starting_tile:
            if tile.previous != None: 
                adj_tile = retrieve_tile(tile, tile.previous[0])
                if tile.previous[0] == 'N': 
                    tile.N = 'Y'
                    adj_tile.S = 'Y'
                if tile.previous[0] == 'E': 
                    tile.E = 'Y'
                    adj_tile.W = 'Y'
                if tile.previous[0] == 'W': 
                    tile.W = 'Y'
                    adj_tile.E = 'Y'
                if tile.previous[0] == 'S': 
                    tile.S = 'Y'
                    adj_tile.N = 'Y'
                if tile.previous[0] == 'U': 
                    tile.U = 'Y'
                    adj_tile.D = 'Y'
                if tile.previous[0] == 'D': 
                    tile.D = 'Y'
                    adj_tile.U = 'Y'

                tile = adj_tile
            elif tile.next != None: 
                adj_tile = retrieve_tile(tile, tile.next[0])

                if tile.next[0] == 'N': 
                    tile.N = 'Y'
                    adj_tile.S = 'Y'
                if tile.next[0] == 'E': 
                    tile.E = 'Y'
                    adj_tile.W = 'Y'
                if tile.next[0] == 'W': 
                    tile.W = 'Y'
                    adj_tile.E = 'Y'
                if tile.next[0] == 'S': 
                    tile.S = 'Y'
                    adj_tile.N = 'Y'
                if tile.next[0] == 'U': 
                    tile.U = 'Y'
                    adj_tile.D = 'Y'
                if tile.next[0] == 'D': 
                    tile.D = 'Y'
                    adj_tile.U = 'Y'

                tile = adj_tile

            while directions_missing(tile) == 0:
                _raise_if_cancelled(cancel_callback)
                
                # Update tile and adjacent tile, then repeat
                if tile.tile_to_S != None and directions_missing(tile.tile_to_S) > 0 and ((tile.next != None and 'S' in tile.next) or (tile.previous != None and 'S' in tile.previous)):
                    adjacent_tile = tile.tile_to_S
                    adjacent_tile.N = 'Y'

                    tile = adjacent_tile

                elif tile.tile_to_W != None and directions_missing(tile.tile_to_W) > 0 and ((tile.next != None and 'W' in tile.next) or (tile.previous != None and 'W' in tile.previous)):
                    
                    adjacent_tile = tile.tile_to_W
                    adjacent_tile.E = 'Y'

                    tile = adjacent_tile

                elif tile.tile_to_E != None and directions_missing(tile.tile_to_E) > 0 and ((tile.next != None and 'E' in tile.next) or (tile.previous != None and 'E' in tile.previous)):
                    adjacent_tile = tile.tile_to_E
                    adjacent_tile.W = 'Y'
                    
                    tile = adjacent_tile

                elif tile.tile_to_N != None and directions_missing(tile.tile_to_N) > 0 and ((tile.next != None and 'N' in tile.next) or (tile.previous != None and 'N' in tile.previous)):
                    adjacent_tile = tile.tile_to_N
                    adjacent_tile.S = 'Y'
                    
                    tile = adjacent_tile

                elif tile.tile_to_D != None and directions_missing(tile.tile_to_D) > 0 and ((tile.next != None and 'D' in tile.next) or (tile.previous != None and 'D' in tile.previous)):
                    adjacent_tile = tile.tile_to_D
                    adjacent_tile.U = 'Y'
                    
                    tile = adjacent_tile

                elif tile.tile_to_U != None and directions_missing(tile.tile_to_U) > 0 and ((tile.next != None and 'U' in tile.next) or (tile.previous != None and 'U' in tile.previous)):
                    adjacent_tile = tile.tile_to_U
                    adjacent_tile.D = 'Y'
                    
                    tile = adjacent_tile
                
                else: break

        if tile.status == 'P': pass
        elif tile.tile_to_N != None and retrieve_tile(tile, 'N').status == 'P' and ((tile.next != None and 'N' in tile.next) or (tile.previous != None and 'N' in tile.previous)): 
            # Check if in next or previous
            tile = retrieve_tile(tile, 'N')
            tile.S = 'Y'
        elif tile.tile_to_E != None and retrieve_tile(tile, 'E').status == 'P' and ((tile.next != None and 'E' in tile.next) or (tile.previous != None and 'E' in tile.previous)): 
            
            tile = retrieve_tile(tile, 'E')
            tile.W = 'Y'

        elif tile.tile_to_W != None and retrieve_tile(tile, 'W').status == 'P' and ((tile.next != None and 'W' in tile.next) or (tile.previous != None and 'W' in tile.previous)): 

            tile = retrieve_tile(tile, 'W')
            tile.E = 'Y'

        elif tile.tile_to_S != None and retrieve_tile(tile, 'S').status == 'P' and ((tile.next != None and 'S' in tile.next) or (tile.previous != None and 'S' in tile.previous)): 
        
            tile = retrieve_tile(tile, 'S')
            tile.N = 'Y'

        elif tile.tile_to_U != None and retrieve_tile(tile, 'U').status == 'P' and ((tile.next != None and 'U' in tile.next) or (tile.previous != None and 'U' in tile.previous)): 
        
            tile = retrieve_tile(tile, 'U')
            tile.D = 'Y'

        elif tile.tile_to_D != None and retrieve_tile(tile, 'D').status == 'P' and ((tile.next != None and 'D' in tile.next) or (tile.previous != None and 'D' in tile.previous)): 
        
            tile = retrieve_tile(tile, 'D')
            tile.U = 'Y'
            
        else: 
            break

    r_tile = None
    # Need to find pseudo seed to copy in new direction: 
    if tile == starting_tile:
        tile.copy_direction = '?'
        t = [tile]

        while len(t) > 0:
            _raise_if_cancelled(cancel_callback)
            ct = t.pop()

            if ct.copy_direction == '?':
                if ct.next != None: 
                    for neighbor in ct.next:
                        _raise_if_cancelled(cancel_callback)
                        adj_tile = retrieve_tile(ct, neighbor)
                        if adj_tile != None:
                            adj_tile.copy_direction = '?' + opp(neighbor)
                            t.append(adj_tile)

                if ct.previous != None: 
                    for neighbor in ct.previous:
                        _raise_if_cancelled(cancel_callback)
                        adj_tile = retrieve_tile(ct, neighbor)
                        if adj_tile != None:
                            adj_tile.copy_direction = '?' + opp(neighbor)
                            t.append(adj_tile)

            else: 
                l = list(ct.copy_direction)
                if ct.next != None: 
                    for neighbor in ct.next:
                        _raise_if_cancelled(cancel_callback)
                        if neighbor != l[1]: 
                            adj_tile = retrieve_tile(ct, neighbor)
                            if adj_tile != None:
                                adj_tile.copy_direction = '?' + opp(neighbor)
                                t.append(adj_tile)

                if ct.previous != None: 
                    for neighbor in ct.previous:
                        _raise_if_cancelled(cancel_callback)
                        if neighbor != l[1]: 
                            adj_tile = retrieve_tile(ct, neighbor)
                            if adj_tile != None:
                                adj_tile.copy_direction = '?' + opp(neighbor)
                                t.append(adj_tile)

            if ct.pseudo_seed: 
                ct.num_times_copied += 1
                if num_dirs(ct)-1 == ct.num_times_copied: 
                    ct.copy_direction = 'r?'
                    r_tile = ct
                else: ct.copy_direction = 'Y'
            elif ct.original_seed:
                ct.num_times_copied += 1
                if num_next(ct) == ct.num_times_copied: 
                    ct.copy_direction = 'r?'
                    r_tile = ct
                else: ct.copy_direction = 'Y'
            else: ct.copy_direction = None

        # If subassembly done copying, prepare the tiles for resetting
        if r_tile != None:
            t = [r_tile]
            while len(t) > 0:
                _raise_if_cancelled(cancel_callback)
                ct = t.pop()

                if ct.copy_direction == 'r?':
                    if ct.next != None: 
                        for neighbor in ct.next:
                            _raise_if_cancelled(cancel_callback)
                            adj_tile = retrieve_tile(ct, neighbor)
                            if adj_tile != None and adj_tile.copy_direction == None:
                                adj_tile.copy_direction = 'r?'
                                t.append(adj_tile)

                    if ct.previous != None: 
                        for neighbor in ct.previous:
                            _raise_if_cancelled(cancel_callback)
                            adj_tile = retrieve_tile(ct, neighbor)
                            if adj_tile != None and adj_tile.copy_direction == None:
                                adj_tile.copy_direction = 'r?'
                                t.append(adj_tile)

                ct.key_tile_N = '*'
                ct.key_tile_E = '*'
                ct.key_tile_W = '*'
                ct.key_tile_S = '*'
                ct.key_tile_U = '*'
                ct.key_tile_D = '*'
                ct.copy_direction = 'r'

    return returned_pseudo_seed

# Run simulation -----------------------------------------------------------------------------------
def run_step_simulation(seed_tile, stage, cancel_callback=None):
    global _step_snapshots

    _raise_if_cancelled(cancel_callback)
    _step_snapshots = []

    try:
        current_stage = 1
        while current_stage < stage:
            _raise_if_cancelled(cancel_callback)

            stack = deque()
            stack.append(seed_tile)
            while len(stack) > 0:
                _raise_if_cancelled(cancel_callback)
                cur_tile = stack.pop()
                if cur_tile.next != None:
                    for neighbor in cur_tile.next:
                        _raise_if_cancelled(cancel_callback)
                        if retrieve_tile(cur_tile, neighbor).copied == False:
                            choose_copy_direction(cur_tile, neighbor, cancel_callback)

                            new_pseudo_seed = copy_assembly(cur_tile, neighbor, cancel_callback)

                            if new_pseudo_seed != None:
                                stack.append(new_pseudo_seed)

                if cur_tile.previous != None:
                    if retrieve_tile(cur_tile, cur_tile.previous[0]).copied == False:
                        direction = cur_tile.previous[0]
                        choose_copy_direction(cur_tile, direction, cancel_callback)

                        new_pseudo_seed = copy_assembly(cur_tile, direction, cancel_callback)

                        if new_pseudo_seed != None:
                            stack.append(new_pseudo_seed)

            hard_reset(cancel_callback)

            current_stage += 1

        return _step_snapshots

    finally:
        _step_snapshots = None
