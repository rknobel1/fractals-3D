from collections import deque
import copy

# To store the tiles where hard resetting will first occur
hard_reset_tiles = []

_TILE_CHANGE_HOOK = None
_OBSERVED_LIST_ATTRS = {"caps", "next", "previous", "new_n", "new_p"}


def set_tile_change_hook(hook):
    global _TILE_CHANGE_HOOK
    _TILE_CHANGE_HOOK = hook


def _tracking_enabled():
    return _TILE_CHANGE_HOOK is not None


def _emit_tile_change(tile, attr_name):
    if _TILE_CHANGE_HOOK is not None:
        _TILE_CHANGE_HOOK(tile, attr_name)


class ObservableList(list):
    def __init__(self, iterable=(), owner=None, attr_name=None):
        super().__init__(iterable)
        self._owner = owner
        self._attr_name = attr_name

    def _notify(self):
        if self._owner is not None and self._attr_name is not None:
            _emit_tile_change(self._owner, self._attr_name)

    def append(self, value):
        super().append(value)
        self._notify()

    def extend(self, values):
        super().extend(values)
        self._notify()

    def insert(self, index, value):
        super().insert(index, value)
        self._notify()

    def remove(self, value):
        super().remove(value)
        self._notify()

    def pop(self, index=-1):
        value = super().pop(index)
        self._notify()
        return value

    def clear(self):
        super().clear()
        self._notify()

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self._notify()

    def __delitem__(self, index):
        super().__delitem__(index)
        self._notify()


def _wrap_observable_list(owner, attr_name, value):
    if value is None or not _tracking_enabled():
        return value
    if isinstance(value, ObservableList):
        wrapped = ObservableList(value, owner=owner, attr_name=attr_name)
        return wrapped
    if isinstance(value, list):
        return ObservableList(value, owner=owner, attr_name=attr_name)
    return value


def instrument_tile_graph(seed_tile):
    """Wrap mutable list fields for an existing tile graph when step tracking is enabled."""
    if seed_tile is None or not _tracking_enabled():
        return

    stack = deque([seed_tile])
    visited = set()
    while stack:
        tile = stack.pop()
        if tile is None or id(tile) in visited:
            continue
        visited.add(id(tile))

        object.__setattr__(tile, '_suspend_notifications', True)
        try:
            for attr_name in _OBSERVED_LIST_ATTRS:
                value = getattr(tile, attr_name, None)
                if isinstance(value, list) and not isinstance(value, ObservableList):
                    object.__setattr__(tile, attr_name, ObservableList(value, owner=tile, attr_name=attr_name))
        finally:
            object.__setattr__(tile, '_suspend_notifications', False)

        for neighbor in ('tile_to_N', 'tile_to_E', 'tile_to_W', 'tile_to_S'):
            stack.append(getattr(tile, neighbor, None))


class Tile():

    def __init__(self, p, n):
        object.__setattr__(self, "_suspend_notifications", True)

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

        # If tile becomes new key tile or not
        self.new_kt_N = False
        self.new_kt_E = False
        self.new_kt_W = False
        self.new_kt_S = False

        # Breadcrumb trail
        self.N = None
        self.E = None
        self.W = None
        self.S = None

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

        object.__setattr__(self, "_suspend_notifications", False)

    def __setattr__(self, name, value):
        # Fast path: when step tracking is disabled, behave like a normal object.
        if not _tracking_enabled():
            object.__setattr__(self, name, value)
            return

        if name in _OBSERVED_LIST_ATTRS:
            value = _wrap_observable_list(self, name, value)

        object.__setattr__(self, name, value)

        if name.startswith("_"):
            return

        if not getattr(self, "_suspend_notifications", False):
            _emit_tile_change(self, name)

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

# Proprogate copy direction through subassembly
def choose_copy_direction(tile, direction):
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

                    copy_direction_update_tiles(cur_tile, direction)
                    copy_direction_update_tiles(adj_tile, direction)

        if cur_tile.previous != None:
            for neighbor in cur_tile.previous:
                if retrieve_tile(cur_tile, neighbor) not in visited_tiles and retrieve_tile(cur_tile, neighbor) != None:
                    adj_tile = retrieve_tile(cur_tile, neighbor)
                    stack.append(adj_tile)

                    copy_direction_update_tiles(cur_tile, direction)
                    copy_direction_update_tiles(adj_tile, direction)

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

                    l = list(adj_tile.copy_direction)

                    l[1] = int(l[1]) - 1

                    if l[1] == 0:
                        adj_tile.copy_direction = l[0]
                        t.append(adj_tile)
                    else:
                        l[1] = str(l[1])
                        adj_tile.copy_direction = "".join(l)
                        break

        if cur_tile.previous != None:
            for neighbor in cur_tile.previous:
                if len(retrieve_tile(cur_tile, neighbor).copy_direction) > 1:
                    adj_tile = retrieve_tile(cur_tile, neighbor)

                    l = list(adj_tile.copy_direction)

                    l[1] = int(l[1]) - 1

                    if l[1] == 0:
                        adj_tile.copy_direction = l[0]
                        t.append(adj_tile)
                    else:
                        l[1] = str(l[1])
                        adj_tile.copy_direction = "".join(l)
                        break

    return

# Updates prev/next if tile is missing
def update_prev_next(ct):

    if ct.tile_to_N != None: ct.N = 'N'
    if ct.tile_to_E != None: ct.E = 'N'
    if ct.tile_to_W != None: ct.W = 'N'
    if ct.tile_to_S != None: ct.S = 'N'

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
def hard_reset():

    while len(hard_reset_tiles) > 0:

        ct = hard_reset_tiles.pop()
        update_prev_next(ct)

        # Retrieve adjacent tile
        adj_tile = retrieve_tile(ct, ct.previous[0])
        update_prev_next(adj_tile)

        # Start by first spreading hard reset if not yet done
        if adj_tile.copy_direction == 'r': 
            adj_tile.copy_direction = 'R?'
            t = [adj_tile]
            update_prev_next(adj_tile)

            while len(t) > 0:
                cur = t.pop()

                if cur.next != None: 
                    for neighbor in cur.next:
                        a = retrieve_tile(cur, neighbor)
                        update_prev_next(a)
                        if a != None and (a.copy_direction == 'r'):
                            if a.next == None: 
                                a.copy_direction = 'R'
                                hard_reset_tiles.append(a)
                            else: a.copy_direction = 'R?'
                            t.append(a)

                if cur.previous != None: 
                    for neighbor in cur.previous:
                        a = retrieve_tile(cur, neighbor)
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
                if num_next(cur) == 0: cur.copy_direction = 'R'
                else: cur.copy_direction = 'R' + str(num_next(cur))

        # Resetting tile
        reset_tile(ct)

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

            elif l[1]+1 == 1 and adj_tile.previous != None: 

                if adj_tile.key_tile_N == '*': adj_tile.key_tile_N = adj_tile.previous[0]
                if adj_tile.key_tile_E == '*': adj_tile.key_tile_E = adj_tile.previous[0]
                if adj_tile.key_tile_W == '*': adj_tile.key_tile_W = adj_tile.previous[0]
                if adj_tile.key_tile_S == '*': adj_tile.key_tile_S = adj_tile.previous[0]
                adj_tile.copy_direction = 'R'
                hard_reset_tiles.append(adj_tile)
            elif l[1]+1 == 1 and adj_tile.previous == None: 
                update_prev_next(adj_tile)
                
                if adj_tile.key_tile_N == '*': adj_tile.key_tile_N = adj_tile.previous[0]
                if adj_tile.key_tile_E == '*': adj_tile.key_tile_E = adj_tile.previous[0]
                if adj_tile.key_tile_W == '*': adj_tile.key_tile_W = adj_tile.previous[0]
                if adj_tile.key_tile_S == '*': adj_tile.key_tile_S = adj_tile.previous[0]
                adj_tile.copy_direction = 'R'
                hard_reset_tiles.append(adj_tile)
            else: 
                l[1] = str(l[1])
                adj_tile.copy_direction = "".join(l) 

            ct.new_kt_N = False
            ct.new_kt_E = False
            ct.new_kt_W = False
            ct.new_kt_S = False

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

            # Update adjacent
            l = list(adj_tile.copy_direction)
            l[1] = int(l[1]) - 1

            if l[1]+1 == 1:
                reset_tile(adj_tile)
                
                if adj_tile.key_tile_N == '*': adj_tile.key_tile_N = None 
                if adj_tile.key_tile_E == '*': adj_tile.key_tile_E = None 
                if adj_tile.key_tile_W == '*': adj_tile.key_tile_W = None 
                if adj_tile.key_tile_S == '*': adj_tile.key_tile_S = None 
            else: 
                l[1] = str(l[1])
                adj_tile.copy_direction = "".join(l) 

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

# Copies a tile from current location to new subassembly
def copy_tile(tile, d, ps):
    pseudo_seed = None
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

    tile_to_copy.terminal = tile.terminal
    tile_to_copy.caps = []

    if tile == ps: 
        tile_to_copy.pseudo_seed = True

        if tile.key_tile_N == None: tile_to_copy.new_kt_N = True
        if tile.key_tile_E == None: tile_to_copy.new_kt_E = True
        if tile.key_tile_W == None: tile_to_copy.new_kt_W = True
        if tile.key_tile_S == None: tile_to_copy.new_kt_S = True
    else: 
        tile_to_copy.new_kt_N = False
        tile_to_copy.new_kt_E = False
        tile_to_copy.new_kt_W = False
        tile_to_copy.new_kt_S = False

    if tile.original_seed: 
        if tile.key_tile_N == None: tile.new_kt_N = True
        if tile.key_tile_E == None: tile.new_kt_E = True
        if tile.key_tile_W == None: tile.new_kt_W = True
        if tile.key_tile_S == None: tile.new_kt_S = True

        tile.copied = True
        tile_to_copy.copied = True

    if tile.copied == True: tile_to_copy.copied = True

    tile.transfer = tile_to_copy
    
    # North
    if d == "N":
        while tile.key_tile_N != None:
            neighbor = retrieve_tile(tile, tile.key_tile_N[0])

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

            tile = neighbor

        if tile.tile_to_N == None:
            tile_to_place = tile.transfer
            if "S" in tile_to_place.next:
                tile_to_place.next.remove("S")
            if len(tile_to_place.next) == 0: tile_to_place.next = None 
            # tile_to_place.previous = ["S"]
            tile.tile_to_N = tile_to_place
            tile_to_place.tile_to_S = tile

            tile.N, tile_to_place.S = None, 'N'

            tile.wall, tile_to_place.wall = True, True

            if tile.key_tile_S[0] == 'N': tile.N = 'M'
            if tile.key_tile_S[0] == 'E': tile.E = 'M'
            if tile.key_tile_S[0] == 'W': tile.W = 'M'
            if tile.key_tile_S[0] == 'S': tile.S = 'M'

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['S']
            if tile.new_n == None: tile.new_n = ['N']
            else: tile.new_n.append('N')
            # tile.new_p = copy.copy(tile.previous)

        else: 
            adj_tile = tile.tile_to_N
            adj_tile.S = 'W'
            adj_tile.transfer = tile.transfer
            tile.transfer = None
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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

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

        prev_tile = retrieve_tile(tile, breadcrumb_direction)

        if len(tile.caps) == num_dirs(tile) and tile.key_tile_S == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:

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

            # Handle caps
            if move_caps(tile):
                prev_tile.caps.append(opp(breadcrumb_direction))
                tile.caps = []

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_S == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:

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

            tile = prev_tile
            prev_tile = retrieve_tile(tile, breadcrumb_direction)

            if len(tile.caps) == num_dirs(tile) and tile.key_tile_S == None and retrieve_tile(tile, breadcrumb_direction).copy_direction == d:

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

        prev_tile.status = 'F'

    # East
    if d == "E":
        while tile.key_tile_E != None:
            neighbor = retrieve_tile(tile, tile.key_tile_E[0])

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

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['W']
            if tile.new_n == None: tile.new_n = ['E']
            else: tile.new_n.append('E')
            # tile.new_p = copy.copy(tile.previous)
        
        else:
            adj_tile = tile.tile_to_E
            adj_tile.W = 'W'
            adj_tile.transfer = tile.transfer
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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

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

        prev_tile.status = 'F'


    # West
    if d == "W":
        while tile.key_tile_W != None:
            neighbor = retrieve_tile(tile, tile.key_tile_W[0])

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

            tile = neighbor

        if tile.tile_to_W == None:
            tile_to_place = tile.transfer
            if "E" in tile_to_place.next:
                tile_to_place.next.remove("E")
            if len(tile_to_place.next) == 0: tile_to_place.next = None 
            # tile_to_place.previous = ["E"]
            tile.tile_to_W = tile_to_place
            tile_to_place.tile_to_E = tile

            tile.W, tile_to_place.E = None, 'N'

            tile.wall, tile_to_place.wall = True, True

            if tile.key_tile_E[0] == 'N': tile.N = 'M'
            if tile.key_tile_E[0] == 'E': tile.E = 'M'
            if tile.key_tile_E[0] == 'W': tile.W = 'M'
            if tile.key_tile_E[0] == 'S': tile.S = 'M'

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['E']
            if tile.new_n == None: tile.new_n = ['W']
            else: tile.new_n.append('W')
            # tile.new_p = copy.copy(tile.previous)

        else: 
            adj_tile = tile.tile_to_W
            adj_tile.E = 'W'
            adj_tile.transfer = tile.transfer
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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

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

        prev_tile.status = 'F'

    # South
    if d == "S":
        while tile.key_tile_S != None:
            neighbor = retrieve_tile(tile, tile.key_tile_S[0])

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

            tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
            tile_to_place.new_p = ['N']
            if tile.new_n == None: tile.new_n = ['S']
            else: tile.new_n.append('S')
            # tile.new_p = copy.copy(tile.previous)

        else: 
            adj_tile = tile.tile_to_S
            adj_tile.N = 'W'
            adj_tile.transfer = tile.transfer
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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'N')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.S
                        neighbor.S = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'E')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.W
                        neighbor.W = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'W')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.E
                        neighbor.E = 'W'

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

                        tile_to_place.new_n = copy.deepcopy(tile_to_place.next)
                        tile_to_place.new_p = copy.deepcopy(tile_to_place.previous)

                    else: 
                        neighbor = retrieve_tile(tile, 'S')

                        neighbor.transfer = tile.transfer
                        tile.transfer = None

                        neighbor.temp = neighbor.N
                        neighbor.N = 'W'

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

        prev_tile.status = 'F'

    return pseudo_seed

# RETURNS: Number of subassemblies completed - total number of subassemblies attached to tile
def directions_missing(tile):
    total, count = 0, 0

    if tile.N != None: total += 1
    if tile.E != None: total += 1
    if tile.W != None: total += 1
    if tile.S != None: total += 1

    if tile.N == 'Y': count += 1
    if tile.E == 'Y': count += 1
    if tile.W == 'Y': count += 1
    if tile.S == 'Y': count += 1

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
    
    return 'DONE'

# Returns len(next) + len(prev)
def num_dirs(tile):
    total = 0
    if tile.next != None: 
        total += len(tile.next)
    if tile.previous != None: 
        total += len(tile.previous)

    return total

# Returns len(next)
def num_next(tile):
    if tile.next == None: return 0
    else: return len(tile.next)

# Returns len(previous)
def num_prev(tile):
    if tile.previous == None: return 0
    else: return 1


def copy_assembly(tile, d): 
    pseudo_seed = None
    returned_pseudo_seed = None
    tile.copied = True

    if d == "N":
        pseudo_seed = tile.tile_to_N
        while tile.key_tile_S != None:
            tile = retrieve_tile(tile, tile.key_tile_S[0])
    if d == "E":
        pseudo_seed = tile.tile_to_E
        while tile.key_tile_W != None:
            tile = retrieve_tile(tile, tile.key_tile_W[0])
    if d == "W":
        pseudo_seed = tile.tile_to_W
        while tile.key_tile_E != None:
            tile = retrieve_tile(tile, tile.key_tile_E[0])
    if d == "S":
        pseudo_seed = tile.tile_to_S
        while tile.key_tile_N != None:
            tile = retrieve_tile(tile, tile.key_tile_N[0])

    starting_tile = tile
    starting_tile.first_tile = True
    while not is_assembly_finished(starting_tile):
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

                tile = adj_tile

            while directions_missing(tile) == 0:
                
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
            
        else: 
            break

    r_tile = None
    # Need to find pseudo seed to copy in new direction: 
    if tile == starting_tile:
        tile.copy_direction = '?'
        t = [tile]

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
                ct = t.pop()

                if ct.copy_direction == 'r?':
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
                ct.copy_direction = 'r'

    return returned_pseudo_seed


# Run simulation -----------------------------------------------------------------------------------
def run_simulation(seed_tile, stage, snapshot_cb=None):
    original_seed_tile = copy.deepcopy(seed_tile)

    def emit_snapshot(label):
        if snapshot_cb is not None:
            snapshot_cb(seed_tile, label)

    emit_snapshot("Initial seed")

    current_stage = 1
    while current_stage < stage:

        stack = deque()
        stack.append(seed_tile)
        while len(stack) > 0:
            cur_tile = stack.pop()
            if cur_tile.next != None:
                for neighbor in cur_tile.next:
                    if retrieve_tile(cur_tile, neighbor).copied == False:
                        choose_copy_direction(cur_tile, neighbor)
                        emit_snapshot(f"Stage {current_stage}: chose copy direction {neighbor}")

                        new_pseudo_seed = copy_assembly(cur_tile, neighbor)
                        emit_snapshot(f"Stage {current_stage}: copied assembly toward {neighbor}")

                        if new_pseudo_seed != None:
                            stack.append(new_pseudo_seed)
                            emit_snapshot(f"Stage {current_stage}: queued new pseudo seed from {neighbor}")

            if cur_tile.previous != None:
                if retrieve_tile(cur_tile, cur_tile.previous[0]).copied == False:
                    direction = cur_tile.previous[0]
                    choose_copy_direction(cur_tile, direction)
                    emit_snapshot(f"Stage {current_stage}: chose copy direction {direction}")

                    new_pseudo_seed = copy_assembly(cur_tile, direction)
                    emit_snapshot(f"Stage {current_stage}: copied assembly toward {direction}")

                    if new_pseudo_seed != None:
                        stack.append(new_pseudo_seed)
                        emit_snapshot(f"Stage {current_stage}: queued new pseudo seed from {direction}")

        hard_reset()
        emit_snapshot(f"Stage {current_stage}: completed hard reset")

        current_stage += 1
        emit_snapshot(f"Completed stage {current_stage - 1}")

    emit_snapshot("Final assembly")

    return [seed_tile, original_seed_tile]
