"""Iterates over a directed graph

This is basically a Kahn sort, but with added requirements.
While running this iterator it is still possible to add and remove nodes.
Moreover some nodes might be in the same exclusive node group where just one node is supposed to be
returned from.
"""

from collections import defaultdict, deque

from .exceptions import CycleException
from .logger import logger


class KahnIterator:
    """Iterates over a directed *dependency* graph

    This iterator allows for members to be removed or added even after starting iterating

    :ivar after: A dict containing all the nodes to be run after
    :ivar lst: A list of all nodes already returned.
    :ivar stack: The stack of nodes to be run next
    :ivar before: A dict containing all the nodes to be run before
    :ivar nodes: All nodes
    """

    def __init__(self, units):
        """Initialize the Iterator with units

        :param units: The units to add to the iterator
        """
        self.after = defaultdict(set)
        self.lst = list()
        self.stack = deque()
        self.before = defaultdict(set)
        self.nodes = set()

        for unit in units:
            self.add_node(unit)

    def copy(self):
        """Copy the iterator
        """
        other = KahnIterator([])
        other.stack = self.stack.copy()
        other.before = self.before.copy()
        other.after = self.after.copy()
        other.lst = self.lst.copy()
        other.nodes = self.nodes.copy()
        return other

    def add_node(self, node):
        """Add another node

        :param node: The node to add
        """
        if node in self.lst:
            return

        for unit in node.after:
            if unit in self.nodes and node not in self.lst:
                self.before[unit].add(node)
        for unit in node.before:
            if unit in self.nodes and node not in self.lst:
                self.after[unit].add(node)

        if len(node.after) > 0:
            self.after[node] = set(filter(
                lambda x: x in self.nodes and x not in self.lst, node.after
            ))
        if len(node.before) > 0:
            self.before[node] = set(filter(lambda x: x in self.nodes, node.before))

        if len(node.after) == 0 or all(after in self.lst for after in self.after[node]):
            self.stack.append(node)

        self.nodes.add(node)

        # Cleanup the stack as new dependencies where added
        nodes_with_new_dependencys = []
        for stack_node in self.stack:
            if len(self.after[stack_node]) > 0:
                nodes_with_new_dependencys.append(stack_node)
        for stack_node in nodes_with_new_dependencys:
            self.stack.remove(stack_node)

    # pylint: disable=too-many-branches
    def remove_node(self, node):
        """Remove a node

        This just works if the node was not run yet. There is no check if the node can be removed.
        Or if it is needed as a dependency. This needs to be done where this function is called.

        :param node: The node to remove
        """
        if node in self.lst:
            raise Exception("Cannot remove unit {} as it was already run".format(node))

        for unit in node.after:
            try:
                self.before[unit].remove(node)
            except KeyError:
                pass

            if len(self.before[unit]) == 0:
                del self.before[unit]

        for unit in node.before:
            try:
                self.after[unit].remove(node)
            except KeyError:
                pass

            if len(self.after[unit]) == 0:
                del self.after[unit]

        try:
            del self.after[node]
        except KeyError:
            pass
        try:
            del self.before[node]
        except KeyError:
            pass
        try:
            self.stack.remove(node)
        except ValueError:
            pass

        self.nodes.remove(node)

        # pylint: disable=redefined-argument-from-local
        for node in self.nodes:
            if node in self.lst:
                continue
            try:
                if len(self.after[node]) == 0:
                    self.stack.append(node)
            except KeyError:
                self.stack.append(node)

    def __iter__(self):
        """Returns the iterator"""
        return self

    def __next__(self):
        """Get next node

        :raises CycleException: This happens if there is a loop of dependency.
        :raises StopIteration: If there is no more node
        """
        if len(self.stack) == 0:
            if len(self.after) > 0 and any(len(x) > 0 for x in self.after.values()):
                # Maybe there are units but they are not on the stack
                for unit, units in self.after.items():
                    if len(units) == 0:
                        self.stack.append(unit)

                # Remove the stack units from after
                for unit in self.stack:
                    del self.after[unit]

                # If stack is empty than this is truly a cycle
                if len(self.stack) == 0:
                    raise CycleException("There was a cylce")

            if len(self.stack) == 0:
                raise StopIteration("No more node")

        node = self.stack.popleft()

        for other in self.before[node]:
            try:
                self.after[other].remove(node)
            except KeyError:
                pass

            if len(self.after[other]) == 0:
                del self.after[other]
                self.stack.append(other)

        # Check if this node belongs to a exclusive config unit.
        for parent in node.belongs:
            if parent.exclusive and any(parent in unit.belongs for unit in self.lst):
                conflict = None
                for unit in self.lst:
                    if parent in unit.belongs:
                        conflict = unit
                        break
                logger.debug(
                    "Ignore Unit %s as the Unit %s of group %s was already run",
                    node,
                    conflict,
                    parent,
                )
                return self.__next__()

        self.lst.append(node)
        return node
