# -*- coding: utf-8 -*-
"""

DUMMY TEST CODE.

This was taken from the typped project and stripped down ONLY to be a
test case for cyfolds.

"""

from __future__ import print_function, division, absolute_import

if __name__ == "__main__": # Run tests when invoked as a script.
    import pytest_helper
    pytest_helper.script_run(["../../test/test_ebnf_classes_and_operators.py",
                              "../../test/test_example_expression_grammar.py",
                              "../../test/test_example_calculator.py",
                              "../../test/test_example_calculator_identifier_keyed_on_values.py",
                              "../../test/test_parser_called_from_parser.py",
                              "../../test/test_pratt_types.py",
                              "../../test/test_basic_usage_section_examples.py",
                              "../../test/test_pratt_parser.py",
                              ], pytest_args="-v")

import sys
import copy
from collections import namedtuple

from .shared_settings_and_exceptions import (HEAD, TAIL, ParserException,
        NoHandlerFunctionDefined, CalledBeginTokenHandler, CalledEndTokenHandler,
        DEFAULT_ALWAYS_TRUE_PRECOND_FUN)
from .lexer import Lexer, TokenNode, TokenTable
from .pratt_types import TypeTable, TypeSig, TypeErrorInParsedLanguage
from .pratt_constructs import ConstructTable
from . import builtin_parse_methods, predefined_token_sets

# TODO: Add an symbol=None option to def_token (maybe also to lexer and
# just pass to that).  It should be used like symbol="(" to define an
# alternative name that can be used in some contexts to refer to the
# token.  If token label not found, could then auto-search symbols... or
# make it explicit.  Essentially just an alias useful in grammar specs.

#
# TokenNode
#

"""The `TokenNode` base class is defined in `lexer.py`.  It contains some of
the basic, general methods that apply to tokens and nodes in token trees.
Methods particular to an application need to be defined in a subclass.  The
function `token_subclass_factory` returns a subclass of `TokenNode` which
represents tokens with a given token label.  The `PrattParser` class sets this
function to be used by its `TokenTable` instance in order to
create a token subclass for each kind of token.  Many methods particular to the
`PrattParser` application are added to the subclass."""

# TODO: Since TokenNode now has a metaclass anyway, why not just use it to
# generate the new instances instead of the factory function?  The factory
# function is maybe simpler, but Sphinx does not properly document the
# TokenNode class defined inside it.
#
# Alternative: Define the base class in module scope in the usual way, and
# then have the factory function just subclass it again (from some trivial
# stub) to represent particular kinds of tokens.

class TokenSubclassMeta(type):
    """A trivial metaclass that will actually create the `TokenSubclass`
    objects.  Since tokens are represented by classes, rather than instances,
    this is necessary in order to change their `__repr__` (the defalt one is
    ugly for tokens) and to overload operators to work for token operands
    in the EBNF-like grammar."""
    def __new__(mcs, name, bases, dct):
        new_class = super(TokenSubclassMeta, mcs).__new__(mcs, name, bases, dct)

        # Below is ugly, but avoids mutual import problems.  Used as an easy
        # way to define token addition so that it works in the grammars defined
        # by the ebnf_classes_and_operators module.
        from .ebnf_classes_and_operators import (
                                     Tok, Not, Prec, nExactly, nOrMore, Repeat)
        # These are saved in a dict below because if they are made attributes
        # then Python 2 complains about "TypeError: unbound method Tok() must
        # be called with TokenClass_k_lpar instance as first argument (got
        # TokenSubclassMeta instance instead)".
        new_class.prod_rule_funs = {
                "Tok": Tok,
                "Not": Not,
                "Prec": Prec,
                "nExactly": nExactly,
                "nOrMore": nOrMore,
                "Repeat": Repeat,
                }
        return new_class

    #
    # Define a nicer-looking __repr__, since the classes represent tokens.
    #

    def __repr__(cls):
        """The representation for tokens.  Tokens are commonly used in the
        code but, being classes, have an ugly default `__repr__` when printed out.
        In this metaclass we can define a better `__repr__` for tokens."""
        string = "TokenClass_{0}".format(cls.token_label)
        return string

    #
    # These overloads work with the ebnf_classes_and_operators module.
    #

    # TODO: Could have a flag to turn overloads on and off, maybe.
    # Might want to turn off when not processing a grammar expression
    # using the tokens, but it really shouldn't matter much.
    def __add__(cls, other):
        """Addition of two tokens is defined to simply return a tuple of
        both tokens.  This is so raw tokens can be used in the operator
        overloaded form of defining production rules for a grammar."""
        return cls.prod_rule_funs["Tok"](cls) + other

    def __radd__(cls, left_other):
        """The right version of `__add__` above."""
        return left_other + cls.prod_rule_funs["Tok"](cls)

    def __or__(cls, other):
        """The `|` symbol simply converts this object into an `ItemList`
        and then calls `__or__` for those objects."""
        return cls.prod_rule_funs["Tok"](cls) | other

    def __ror__(cls, left_other):
        """The right version of `__or__` above."""
        return left_other | cls.prod_rule_funs["Tok"](cls)

    def __rmul__(cls, left_other):
        """The expression `n*token` for an int `n` is "n occurrences of"
        `token`."""
        return cls.prod_rule_funs["Repeat"](left_other, cls)

    def __rpow__(cls, left_other):
        """The expression `n**token` for an int `n` is "n or more occurrences of"
        `token`."""
        return cls.prod_rule_funs["nOrMore"](left_other, cls)

    def __invert__(cls):
        """Define the `~` operator for production rule grammars."""
        return cls.prod_rule_funs["Not"](cls)

    def __getitem__(cls, arg):
        """Define the bracket indexing operator for production rule grammars
        to set the precedence."""
        return cls.prod_rule_funs["Prec"](cls, arg)

def token_subclass_factory():
    """This function is called from the `create_token_subclass` method of
    `TokenTable` when it needs to create a new subclass to begin
    with.  It should not be called directly.

    Create and return a new token subclass which will be modified and used
    to represent a particular kind of token.  Specifically, each scanned token
    matching the regex defined for tokens with a given token label is
    represented as an instance of the subclass created by calling this function
    (with further attributes, such as the token label, added to it).

    Using a separate subclass for each token label allows for attributes
    specific to a kind of token (including head and tail handler methods) to
    later be added to the class itself without conflicts.  This function
    returns a bare-bones subclass without any head or tail functions, etc."""

    class TokenSubclass(TokenSubclassMeta("TokenSubclass", (object,), {}), TokenNode):
    #class TokenSubclass(TokenNode, metaclass=TokenSubclassMeta):  # Python 3
    #class TokenSubclass(TokenNode):                               # No metaclass.
        """The factory function returns this class to represent tokens.  It is a
        subclass of the `TokenNode` class, defined in the lexer module."""
        static_prec = 0 # The prec value for this kind of token, with default zero.
        token_label = None # Set to the actual value later, by create_token_subclass.
        #parser_instance = None # Set by recursive_parse. AVOID if not needed.

        def __init__(self, value):
            """Initialize an instance of the subclass for a token of the kind
            labeled with `token_label`.  The `value` is the actual parsed
            string from the text.  This instance represents the token."""
            super(TokenSubclass, self).__init__() # Call base class __init__.
            self.value = value # Set from lex.token_generator; static value=None.

            # The `expanded_formal_sig` attr is set upon parsing.  It is the
            # expanded form of one of the formal sigs which were registered
            # with the token (the expansion handles wildcards, repeat options,
            # etc.)  It is the signature which matched the actual args.  The
            # `self.expanded_formal_sig` has an attribute `original_formal_sig`
            # which is the original, unexpanded formal signature that matched
            # (after expansion) the actual arguments.  After parsing it is set
            # as the token attribute `original_formal_sig`.  This is important
            # because the `eval_fun` and `ast_data` for tokens are saved in
            # dicts keyed by the original signature at the time when they are
            # defined (via `modify_token`).  So we need the resolved original
            # signature to look up the value.  (Note that if overloading on
            # return types is turned off then these dicts are keyed only on the
            # argument portion of the original typesig.)
            self.original_formal_sig = "Unresolved" # The matching orig sig.
            self.expanded_formal_sig = "Unresolved" # Expanded version of above.
            self.actual_sig = "Unresolved" # The actual signature.

        @classmethod
        def prec(cls):
            """Return the precedence for the token.  This is currently a static
            value for each type of token.  Later it may be dynamic value
            associated with the particular tail function which is selected in a
            given context. Update: may become an attribute of a construct and
            no longer of a token."""
            return cls.static_prec

        def process_not_in_tree(self):
            """Removes any immediate children which have `not_in_tree` set."""
            modified_children = []
            for child in self.children:
                if not hasattr(child, "not_in_tree"):
                    modified_children.append(child)
                else:
                    modified_children += child.children
            self.children = modified_children

        def process_and_check_node(self, construct,
                                   val_type_override=None, all_vals_override=None,
                                   typesig_override=None):
            """This routine is automatically called just after a handler
            function returns a subtree.  It is called for the root of the
            returned subtree.  It sets some attributes and checks that the
            actual types match some defined type signature for the function.

            If `val_type_override` is set to a `TypeObject` instance then the
            return type of both the `expanded_formal_sig` and the `actual_sig`
            for the node is set to that type *after* the first pass of
            processing and type-checking for the subtree is finished.  (This
            option does not currently work for two-pass checking when
            overloading on return types is used.)  This option is useful for
            handling things like parentheses and brackets which inherit the
            type of their child (assuming the parens and brackets are kept as
            nodes in the parse tree and not eliminated).  The override value is
            used for type-checking farther up the expression tree.

            If `all_vals_override` is set to a `TypeObject` instance then all
            the possible signatures have their `val_type` changed to that type
            *before* any checking is done.  This should work for both one and
            two-pass checking, but no check is made for producing duplicate
            types due to the `val_type` changes.

            The `typesig_override` argument must be a `TypeSig` instance.  If
            set it will be *assigned* to the node as its only possible
            `expanded_formal_sig` before type checking (instead of looking up
            the registered ones).  Type checking then proceeds as usual."""

            # Get all the sigs registered for the node's construct.
            if typesig_override is not None:
                all_possible_sigs = [typesig_override]
            else:
                all_possible_sigs = construct.original_sigs
            if all_vals_override:
                all_possible_sigs = [TypeSig(all_vals_override, s.arg_types)
                                                      for s in all_possible_sigs]
            self.all_possible_sigs = all_possible_sigs # Temporary attribute.

            # Do the actual checking.
            if not self.parser_instance.overload_on_ret_types: # One-pass.
                self._check_types_one_pass()
            else: # Two-pass.
                self._check_types_first_of_two_passes()
                # If we have a *unique* matching sig, run pass two on the
                # subtree.  In this case, since the signature is fixed by
                # argument types (regardless of where the top-down pass
                # starts from) we can in this case resolve the types in the
                # subtree early.  Note `check_types_in_tree_second_pass` is
                # also called on the root node from the `parse` method.
                if len(self.matching_sigs) == 1: # matching_sigs set by _check_types
                    self.check_types_in_tree_second_pass()

            # Implement val_type override if set.
            if val_type_override:
                # Note that the original_formal_sig attribute was already set.
                # The ast_data and eval_fun are keyed on that.
                self.expanded_formal_sig = TypeSig(val_type_override,
                                                   self.expanded_formal_sig.arg_types)
                self.actual_sig = TypeSig(val_type_override, self.actual_sig.arg_types)

        def _check_types_one_pass(self):
            """Utility function called from `process_and_check_node` to check
            the actual types against their signatures when overloading is only on
            argument types."""
            all_possible_sigs = self.all_possible_sigs

            # One-pass, each child c has a unique c.expanded_formal_sig already set.
            list_of_child_sig_lists = [[c.expanded_formal_sig] for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)
            # Below all_possible_sigs is saved ONLY for printing error messages.
            self.all_possible_sigs = all_possible_sigs

            # No overloading on return types so we can finalize the actual types.
            if len(self.matching_sigs) != 1:
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution: The actual argument types match"
                        " multiple signatures.")

            # Found a unique signature; set the node's expanded_formal_sig attribute.
            # Saved sig used for eval_fun resolution, ast_data, semantic action, etc.
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type,
                                      [c.actual_sig.val_type for c in self.children])

            # Delete some temporary attributes no longer needed.
            delattr(self, "matching_sigs")
            delattr(self, "all_possible_sigs")

        def _check_types_first_of_two_passes(self):
            """Utility function called from `process_and_check_node` to do the
            first pass in checking the actual types against their signatures.
            Two-pass checking is needed for overloading on return types.  First
            pass goes up the tree, second pass goes back down."""
            all_possible_sigs = self.all_possible_sigs

            # First pass case, multiple sigs in child's self.matching_sigs list.
            list_of_child_sig_lists = [c.matching_sigs for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)

        def check_types_in_tree_second_pass(self, root=False):
            """Recursively run the second pass on the token subtree with the
            `self` node as the root.

            This method currently still needs to be explicitly called for the
            root of the final parse tree, from the `PrattParser` method
            `parse`, as well as from the checking routines here to do partial
            checks on subtrees which are already resolvable."""
            unresolved_children = [
                    c for c in self.children if hasattr(c, "matching_sigs")]
            self._check_types_pass_two() # Call first on self to do top-down.
            for child in unresolved_children: # Recurse on unprocessed children.
                child.check_types_in_tree_second_pass()
            # Delete childrens' matching_sigs lists after they are no longer needed.
            # This also acts as an indicator that the node has been resolved.
            for child in unresolved_children:
                delattr(child, "matching_sigs")
            if root:
                # The final pass in _check_types that deletes these attrs doesn't get
                # run on root, so it is explicitly done here when `root` flag is true.
                delattr(self, "matching_sigs")
                delattr(self, "all_possible_sigs")

        def _check_types_pass_two(self):
            """A second pass is only used when overloading on return types is
            allowed.  It is a top-down pass where each node chooses a unique
            final signature for each of its children.  It depends on the
            node attribute `self.matching_sigs` having been set in the first
            pass."""
            # On FIRST pass: on the way *up* the tree (after getting the
            # literal tokens, the leaves of the tree) get all the signature
            # types for a node which match in arguments for *some* possible
            # return-type choice of the children.  Same as the one-pass
            # version, but now sets of possibilities are allowed and state is
            # saved for the second pass to use: the list of matching sigs is
            # temporarily saved with the node in the self.matched_sigs
            # attribute.
            #
            # Summary: first pass, bottom-up, find all sigs that match possible
            # val_types of the node's children, across all arguments.
            #
            # After the first pass the root should have a unique sig; if not
            # there is ambiguity.  (Each node saved a set of sigs that is
            # satisfiable by some realizable choice of child sigs, and parents
            # can force children to assume any of their possible types).
            #
            # On SECOND pass: On the way *down* the tree, parents choose one
            # sig as final for each child and set it in that child's node as
            # the new self.matching_sigs.  This should always be a unique sig;
            # otherwise there is ambibuity.  Recursively called on children.
            #
            # Summary: second pass, top-down, root is unique and parents assign
            # and set the (unique) signature for each of their children.
            #
            # Note that this algorithm works just as well if the second pass is
            # run on each subtree as soon as the subtree root has a unique
            # signature, and the recursion only goes down to subtrees with
            # roots having a unique signature.  This yields partial results and
            # some error conditions sooner, and is what is implemented here.

            if len(self.matching_sigs) != 1: # The root case needs this.
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution (second pass).  Possible type "
                        "assignments for the children/arguments of the token node match"
                        " {0} possible node signatures: {1}.  Uniqueness is required."
                        .format(len(self.matching_sigs), self.matching_sigs))

            # We have a unique signature; set the node's type attributes
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            # Start setting the actual signature; children will fill arg types
            # when resolved.
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type, [])

            # Set the actual_sig arg_type for the parent (appending in sequence with others).
            if self.parent is not None:
                parent_args_so_far = list(self.parent.actual_sig.arg_types)
                parent_args_so_far.append(self.expanded_formal_sig.val_type)
                self.parent.actual_sig = TypeSig(self.parent.actual_sig.val_type,
                                                 parent_args_so_far)

            # Update the matching_sigs attribute for each child (should be singleton).
            for count, child in enumerate(self.children):
                if not hasattr(child, "matching_sigs"):
                    continue # Already resolved.
                matched_sigs = TypeSig.get_child_sigs_matching_return_arg_type(
                                      child, self.expanded_formal_sig.arg_types[count],
                                      child.matching_sigs)
                # From the first pass, we know at least one child sig matches.
                assert len(matched_sigs) != 0 # Debug.
                if len(matched_sigs) > 1:
                    # Recursion could catch this on the next step, but better err msg.
                    child._raise_type_mismatch_error(matched_sigs,
                        "Token node has multiple signatures with return type matching "
                        "type of parent (pass two). Parent expects type '{0}'.  Defined"
                        " signatures are: {1}."
                        .format(self.expanded_formal_sig.val_type, child.matching_sigs))
                child.matching_sigs = matched_sigs
            return

        def _raise_type_mismatch_error(self, matching_sigs, basic_msg):
            """Raise an error, printing a helpful diagnostic message.  Assumes
            that `_check_types` has been called (to set `self.all_possible_sigs`)."""
            # TODO: Will the self.expanded_formal_sig *ever* be resolved when this routine is
            # called?  If not, then it is not very useful and message could be reworded.
            diagnostic = ("  The current token has value '{0}' and label '{1}'.  "
                         " Its expanded formal signature is {2}.  The"
                         " children/arguments have token labels and values of {3} and "
                         "value types {4}.  The list of matching signatures "
                         "is {5}.  The list of possible signatures was {6}"
                         .format(self.value, self.token_label,
                             self.expanded_formal_sig,
                             list(c.summary_repr() for c in self.children),
                             # Note this below can be "Unresolved", better message?
                             list(c.expanded_formal_sig.val_type
                                  if not isinstance(c.expanded_formal_sig, str)
                                  else c.expanded_formal_sig for c in self.children),
                             matching_sigs, self.all_possible_sigs))
            raise TypeErrorInParsedLanguage(basic_msg + diagnostic)

        #
        # Evaluations and semantic actions.
        #

        @property
        def eval_fun(self):
            """Return the evaluation function saved with the winning construct
            dispatched for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_eval_fun(orig_sig, token_value_key=self.value)

        @property
        def ast_data(self):
            """Return the ast data saved with the winning construct dispatched
            for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_ast_data(orig_sig, token_value_key=self.value)

        def eval_subtree(self):
            """Run the saved evaluation function on the token, if one was
            registered with it.  Returns `None` if no evaluation function is found."""
            orig_sig = self.original_formal_sig # Set during parsing.
            eval_fun = self.eval_fun # Property method above.

            # TODO: Consider if returning None is better than raising exception...
            if not eval_fun:
                return None

            # TODO: Consider if special exception should be raised.
            #if not eval_fun:
            #    raise ParserException("An evaluation function is needed for token with "
            #            "value '{0}' and label '{1}' but no defined and matching "
            #            "evaluation function was found in the dict of eval functions.  "
            #            "The resolved original signature is {2} and the resolve expanded"
            #            " signature is {3}.  The resolved construct_label is {4}.  The "
            #            "token's eval_fun_dict is:\n   {5}."
            #            .format(self.value, self.token_label, orig_sig, sig,
            #                    self.construct_label, self.eval_fun_dict))

            return eval_fun(self)

        #
        # The main recursive_parse function.
        #

        def get_jop_token_instance(self, lex, processed_left, extra_data, subexp_prec):
            """Returns an instance of the jop token iff one should be inferred in the
            current context; otherwise returns `None`."""
            # TODO: extra_data arg now holds subexp_prec as field.
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler

            # Not if jop token is undefined for the parser.
            if not parser_instance.jop_token_subclass:
                return None

            # Not if at end of expression.
            if lex.peek().is_end_token():
                return None

            # Not if the ignored token for jop is set but not present.
            if parser_instance.jop_ignored_token_label and (
                          parser_instance.jop_ignored_token_label
                          not in lex.peek().ignored_before_labels()):
                return None

            # Now infer a jop, but only if 1) its prec would satisfy the while loop
            # in `recursive_parse` as an ordinary token, 2) the next token has
            # a head handler defined in the conditions when the jop will need
            # to run its head handler, and 3) the next token similarly has no
            # tail handler in the context.
            if parser_instance.jop_token_subclass.prec() > subexp_prec:
                # Provisionally infer a jop; create a subclass instance for its token.
                #
                # Todo: Maybe for jop and null-string tokens define methods
                # get_jop_token_instance() which gets the token but calls the
                # lexer to dress it up more like a "real" token, with ignored_before
                # and line numbers, etc. (without putting it in the buffer, of course).
                jop_instance = parser_instance.jop_token_subclass(None)
                jop_instance.extra_data = extra_data

                # This is a little inefficient (since it uses a `go_back` call)
                # but we need to be sure that when the tail handler of the jop
                # is called and it reads a token that that token has a head
                # handler defined for it *in that precondition context*.
                # Otherwise, no jop will be inferred.  We also make sure that
                # it has no tail handler in the context, since then it would be
                # a lower-precedence (lower precedence because we broke out of
                # the loop above) infix or postfix operator, and no jop is
                # inferred before another operator).
                curr_token = lex.next()
                try:
                    # Dispatch here WITHOUT CALLING, since calling will consume
                    # another token; also, deeper-level recursions could cause false
                    # results to come up the recursion chain.  We are just testing
                    # what handlers are defined for the token.
                    _peek_head_handler, head_construct = dispatch_handler(
                                                   HEAD, curr_token, lex, extra_data)
                    try: # Found head handler, now make sure it has no tail handler.
                        _peek_tail_handler, tail_construct = dispatch_handler(
                                   TAIL, curr_token, lex, extra_data, processed_left)
                    except NoHandlerFunctionDefined:
                        # This is the only case where an actual token is returned.
                        return jop_instance
                    else:
                        return None
                except NoHandlerFunctionDefined:
                    return None # No precondition matches, assume no jop.
                finally:
                    #delattr(curr_token, "extra_data") # Only needed if pushback below, not go_back.
                    lex.go_back(1)
            else:
                return None

        def dispatch_null_string_handler(self, head_or_tail, lex, subexp_prec,
                                         extra_data, processed_left=None):
            """Check for any possible matching null-string token handlers;
            return the token and the matching handler if one is found.

            Note that the precedence for a null-string token is set to
            `subexpr_prec`, so it would always have activated the while loop if
            it were a real token."""
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            # See if a null-string token is set and a handler matches preconds.
            if not parser_instance.null_string_token_label:
                return None, None, None
            else:
                # TODO: Later don't re-create each time, save one.
                null_string_token = parser_instance.null_string_token_subclass(None)
            null_string_token.extra_data = extra_data

            curr_token = None
            handler_fun = None
            construct = None
            try:
                handler_fun, construct = dispatch_handler(head_or_tail,
                                                          null_string_token,
                                                          lex, extra_data, processed_left)
                curr_token = null_string_token
            except NoHandlerFunctionDefined:
                pass
            return curr_token, handler_fun, construct

        def recursive_parse(self, subexp_prec, only_head=False):
            """Parse a subexpression as defined by token precedences. Return
            the result of the evaluation.  Recursively builds up the final
            result in `processed_left`, which is the tree for the part of the
            full expression to the left of the current token.

            The list `lookbehind` saves all the previously evaluated
            subexpressions at this level of recursion (i.e., at the top level
            in the same subexpression) and passes it to the dispatched tail
            handlers, in case that routine wants to make use of it.  For
            example, the ordinal position of the token in the top level of the
            subexpression can be calculated from the length of `lookbehind`.

            This function is made a method of `TokenSubclass` so that handler
            functions can easily call it by using `tok.recursive_parse`, and
            also so that it can access the lexer without it needing to be
            passed as an argument.  It is basically a static function,
            though.

            The `extra_data` attribute is set for all triggering tokens, and is
            guaranteed to be available for precondition functions and for
            handler functions.  It is set before any dispatches or recursive calls,
            and is deleted from the token after the recursive call.  It is an
            advanced feature which most users will not need."""
            # Note that all the dispatching functions set the `extra_data`
            # attribute of their token before the dispatching is done, but they
            # do not update `extra_data` itself in any way.

            # Note on below code: It is tempting for efficiency to define a jop
            # and null-string token instance, save it, and only use it when
            # necessary (replacing it only when used).  But some things need to
            # be considered.
            #
            # Now that handlers are not with tokens, that is no longer a
            # concern... TODO go ahead and do this.
            #
            # Is there any special attribute or other thing that is assigned on
            # creation which might change?  Either way, you should probably add
            # extra things like line numbers to mimic ordinary tokens. Note
            # that currently you only really pay the creation cost if you
            # actually use the jop or null-string feature, but a lot of dummy
            # instances are created if you do.

            # This err check catches some cases of tokens defined via Lexer, not all.
            if not hasattr(self, "token_kind"):
                raise ParserException("All tokens used in the parser must be"
                        " defined in via parser's methods, not the lexer's.")

            #
            # Initialize, and set some shorter aliases.
            #

            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            lex = self.token_table.lex
            extra_data = ExtraDataTuple(lookbehind=[], constructs=[],
                                        subexp_prec=subexp_prec)

            #
            # Start the actual Pratt parsing recursion.
            #

            curr_token, head_handler, construct = self.dispatch_null_string_handler(
                                                     HEAD, lex, subexp_prec, extra_data)
            if not curr_token: # No null-string token fired, so use normal next() call.
                curr_token = lex.next()
                head_handler, construct = dispatch_handler(
                                                     HEAD, curr_token, lex, extra_data)

            extra_data.constructs.append(construct)

            # TODO: Should the root of processed_left be set for is_head instead, for
            # general case?  Or set "head_trigger_token" to label instead of None?
            # Consider how lookup will work in usual and general cases of arbitrary
            # token as subtree root.
            curr_token.is_head = True # Used to look up eval_fun and ast_data later.

            processed_left = head_handler()

            delattr(curr_token, "extra_data") # Delete after recurse, allow mem cleanup.
            extra_data.lookbehind.append(processed_left)
            extra_data.constructs.append(construct)

            if only_head:
                return processed_left

            while True:

                #
                # The loop below is the main loop in ordinary Pratt parsing.  The
                # Outer loop is ONLY for the special case when a jop is defined.
                #

                # TODO: Consider modification like code below to allow
                # precedences per constuct, which also makes "prec - 1" no
                # longer necessary for right assoc when property is set for the
                # construct itself.  See what performance hit it has, one
                # go_back per subexpression.  Note that jops use a single
                # go_back already when they are defined...
                #
                # The ugly comment-string code below works.  It just pulls the
                # token-dispatching out to before the precedence test.
                # Obviously could then use some cleanup and refactoring, too.
                # Consider possible interactions with jop and null-string
                # tokens, but they don't do a `next` call anyway.  (Is it
                # better to pull out the ns_token dispatch, at least?  In
                # regular code, how to get null-string to appear at end of a
                # subexpression?)
                #
                # Argument it works: This code is doing exactly the same
                # dispatching as it would inside the loop test, but it is doing
                # it before the loop test.  The loop test never modifies
                # anything.  If the test fails the effects of the dispatches
                # are undone.
                """
                while True:
                    #err = None
                    ns_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if ns_token:
                        curr_token = ns_token
                        peek_prec = lex.token.prec()
                        #peek_prec = construct.prec() # Switch to this...
                    else:
                        curr_token = lex.next()
                        try:
                            tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                            lex, extra_data, processed_left)
                            peek_prec = lex.token.prec()
                            #peek_prec = construct.prec() # Switch to this...
                        except NoHandlerFunctionDefined as e:
                            # If no construct at all then can't have tail handler so
                            # prec should be 0.  But if it fails due to a precond,
                            # token itself could still have a prec > 0.  In that case
                            # it will get inside the loop and fail, but it really
                            # shouldn't have gotten inside.
                            #
                            # Only one test changes, and new one is commented out in
                            # the test file under the old one.
                            #err = e
                            peek_prec = -1 # Always fail test and break.
                            #peek_prec = lex.token.prec()

                    #test_assoc = False if err else (peek_prec == subexp_prec and
                    #                                construct.assoc == "right")
                    test_assoc = peek_prec == subexp_prec and construct.assoc == "right"
                    if peek_prec > subexp_prec or test_assoc:
                        #if err: # Error would have been found inside loop, now above.
                        #    raise err # Avoid error msg changing (makes test fail).
                        processed_left = tail_handler()
                        delattr(curr_token, "extra_data")
                        extra_data.lookbehind.append(processed_left)
                        extra_data.constructs.append(construct)
                    else:
                        if not ns_token:
                            lex.go_back(1)
                        break
                """

                while lex.peek().prec() > subexp_prec:

                    curr_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if not curr_token: # No null handler fired off, get regular way.
                        curr_token = lex.next()
                        tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                        lex, extra_data, processed_left)

                    processed_left = tail_handler()
                    delattr(curr_token, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)

                #
                # Broke out of main loop, determine whether or not to infer a jop.
                #

                jop_instance = self.get_jop_token_instance(
                                         lex, processed_left, extra_data, subexp_prec)
                if jop_instance:
                    jop_tail_handler, construct = dispatch_handler(TAIL, jop_instance,
                                                        lex, extra_data, processed_left)
                    processed_left = jop_tail_handler()
                    delattr(jop_instance, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)
                else:
                    break

            return processed_left

        #
        # Copying instances of tokens.
        #

        def __copy__(self):
            """Return a shallow copy of the token."""
            return copy.copy(self)

        #
        # Some representations that apply to the subclasses.
        #

        def summary_repr_with_types(self):
            """A short summary repr of the node, without its children."""
            return ("<" + str(self.token_label) +
                    ",'" + str(self.value) +
                    "'," + str(self.expanded_formal_sig.val_type) + ">")

        def tree_repr_with_types(self, indent=""):
            """Token representation as the root of a parse subtree, with formatting.
            The optional `indent` parameter can be either an indent string or else
            an integer for the number of spaces to indent.  Note that the ordinary
            `tree_repr` method without types is also available, inherited from
            the base node object."""
            try:
                num_indent = int(indent)
            except ValueError:
                pass
            else:
                indent = " " * num_indent
            string = indent + self.summary_repr_with_types() + "\n"
            for c in self.children:
                string += c.tree_repr_with_types(indent=indent+" "*4)
            return string

        def string_repr_with_types(self):
            """A string repr for the tree that includes type information."""
            string = self.summary_repr_with_types()
            if self.children:
                string += "("
                string += ",".join(c.string_repr_with_types() for c in self.children)
                string += ")"
            return string

        @classmethod
        def class_repr(cls):
            """Print out the `TokenSubclass` classes (representing tokens) in a
            nice way.  The default is hard to read."""
            string = "Token({0})".format(cls.token_label)
            return string

    return TokenSubclass # Return from token_subclass_factory function.

#
# Parser
#

def lexer_add_parser_instance_attribute(lexer, token):
    """Passed to lexer to add a `parser_instance` attribute to each token it
    returns.  This attribute is added to instances at the lexer, from its
    current token table, because of the case where parsers call other parsers.
    (It is not added to general token subclasses in `def_token_master` because
    parsers could potentially share token subclasses.)"""
    token.parser_instance = lexer.token_table.parser_instance # From token table.
    return token

# Could also add parser_instance and construct as fields of the extra data tuple.
# Could extra_data also be passed to handler functions?  Nice to have construct
# instance available there, perhaps.  TODO: Consider.
ExtraDataTuple = namedtuple("ExtraHandlerData", ["lookbehind",
                                                 "constructs",
                                                 "subexp_prec"])

class PrattParser(object):
    """A parser object.  Each parser object contains a table of defined tokens,
    a lexer, a table of constructs, and a table of defined types."""
    def __init__(self, max_peek_tokens=None,
                       max_deque_size=None,
                       lexer = None,
                       default_begin_end_tokens=True,
                       type_table = None,
                       skip_type_checking=False,
                       overload_on_arg_types=True,
                       overload_on_ret_types=False,
                       partial_expressions=False,
                       parser_label=None,
                       raise_on_equal_priority_preconds=False):
        """Initialize the parser.

        The `max_peek_tokens` parameter is an optional arbitrary limit on the
        level of peeks allowed in the lexer.  Setting to 1 limits it to a
        single token lookahead.  The default setting `None` gives
        peek-on-demand as far ahead as requested.

        The `max_deque_size` parameter is an optional limit on the size of the
        deque that the lexer keeps for previous tokens, the current token, and
        requested peek tokens.  The default is for it to grow arbitrarily
        (though it is reset on each parse).  Needs to be large enough for the
        max level of peeks required plus the max `go_back` level required.

        If a `Lexer` instance is passed in the parser will use that lexer and
        its token table, otherwise a new lexer is created.  The any other lexer
        options are ignored.

        No default begin and end functions will be set if a lexer is passed in,
        regardless of the value of `default_begin_end_tokens`.  Otherwise,
        default begin and end tokens will be defined unless
        `default_begin_end_tokens` is set false (note that creating them by
        default is the opposite of the default behavior for the lower-level
        Lexer class).

        Setting `skip_type_checking=True` is slightly faster since typing is
        not being used at all.  Note that overloading depends on type-checking
        to resolve the actual types, so this flag implies that the overload
        flags are all false.  The default is false.  It should be possible to
        define types, use them during testing, and then turn checking off ---
        provided overloading is not used to get different evaluation functions
        or AST data elements for different overloads.

        The `overload_on_arg_types` flag specifies whether or not to overload
        on argument types.  The default is true.  Cannot be changed after
        initialization.

        Setting `overload_on_ret_types` also overloads on argument types.  It
        requires an extra walk of the token tree, and implies overloading on
        argument types.  The default is false.  Cannot be changed after
        initialization.

        If `partial_expressions` is set true then no check will be made in the
        `parse` method to see if the parsing consumed up to the end-token in
        the lexer.  Multiple expression text can be parsed by repeatedly
        calling `parse` when this option is true and checking whether the
        lexer's current token is the end-token.

        The `parser_label` is an optional descriptive string for a parser.
        These can be useful in debugging when they appear in error messages,
        especially when working with multiple parser instances.

        If `raise_on_equal_priority_preconds` is true then an exception will be
        raised if two precondition functions are registered with the same
        trigger token in the same head or tail position which have the same
        precondition priority.  The default is false, and the first-defined
        matching precondition function of the same priority will win any
        competition when several are true.  This option can be used to ensure
        at language define-time that there is no definition-order dependence in
        dispatching.  If two such preconditions functions are mutually
        exclusive there is no problem with them having the same priority, but
        this condition cannot be checked by a program.  A small difference can
        be added."""

        if parser_label:
            self.parser_label = parser_label # Set first, for error messages.
        else:
            self.parser_label = None

        ## Type-checking options below; these cannot be changed after initialization.
        if overload_on_ret_types:
            overload_on_arg_types = True # Overload on ret implies overload on args.
        self.skip_type_checking = skip_type_checking # Skip all type checks, faster.
        if not skip_type_checking:
            self.overload_on_arg_types = overload_on_arg_types
            self.overload_on_ret_types = overload_on_ret_types
        else: # Overloading requires type checking.
            self.overload_on_arg_types = False
            self.overload_on_ret_types = False

        # If exceptions are not raised on ties then with non-mutually-exclusive
        # precond functions the first-set one will have precedence when they
        # are both true.  Need to define this before registering any handlers (
        # which is done below in `def_begin_end_tokens`).
        self.raise_on_equal_priority_preconds = raise_on_equal_priority_preconds
        #self.raise_on_equal_priority_preconds = True # DEBUG

        self.construct_table = ConstructTable(parser_instance=self) # Dict of constructs.
        self.default_construct_label_number = 0 # For unique precondition labels.

        if lexer: # Lexer passed in.
            self.lex = lexer
            self.token_table = lexer.token_table
        else: # No Lexer passed in.
            self.token_table = TokenTable(
                                token_subclass_factory_fun=token_subclass_factory)
            self.lex = Lexer(self.token_table,
                             max_peek_tokens=max_peek_tokens,
                             max_deque_size=max_deque_size,
                             default_begin_end_tokens=False)
            # Set the begin and end tokens unless the user specified not to.
            if default_begin_end_tokens:
                self.def_begin_end_tokens() # Use function's defaults.
        self.lex.default_helper_exception = ParserException # Default for match_next, etc.
        # Add mod function to lexer here, works even if they passed in a lexer.
        self.lex.final_mod_function = lexer_add_parser_instance_attribute

        self.token_table.parser_instance = self # Give token table ref to parser.

        if type_table:
            self.type_table = type_table
        else:
            self.type_table = TypeTable(self)

        self.num_lookahead_tokens = max_peek_tokens
        self.jop_token_label = None # Label of the jop token, if any.
        self.jop_token_subclass = None # The actual jop token, if defined.
        self.null_string_token_label = None # Label of the null-string token, if any.
        self.null_string_token_subclass = None # The actual null-string token, if any.

        self.partial_expressions = partial_expressions # Whether to parse multiple expressions.

        self.pstate_stack = [] # Stack of production rules used in grammar parsing.
        self.top_level_production = False # If true, require grammar parses to consume to end.
        self.disable_pstate_processing = False # Set to temporarily disable grammar parsing.

    #
    # Methods defining tokens.
    #

    def def_token_master(self, token_label, regex_string=None, on_ties=0, ignore=False,
                         token_kind="regular", ignored_token_label=None,
                         matcher_options=None):
        """The master method for defining tokens; all the convenience methods
        actually call it.  Allows for factoring out some common code and
        keeping the attributes of all the different kinds of tokens up-to-date.
        This routine calls the underlying lexer's `def_token` to get tokens and
        then adds extra attributes needed by the `PrattParser` class.

        The `token_kind` argument must be one of the following strings:
        `"regular"`, `"ignored"`, `"begin"`, `"end"`, `"jop"`, or
        `"null-string"`.  The `ignored_token_label` is used only when defining
        a jop.

        Tokens can be shared between parsers if all their properties are the
        same.  Note that for now this includes the precedence value for any
        tail handlers (since that is made a token attribute).  Null-string and
        jop tokens are the exception, but they are special in that they are
        never returned by the lexer, only by a particular parser."""
        token_table = self.token_table

        if token_kind == "regular":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=ignore, matcher_options=matcher_options)

        elif token_kind == "ignored":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=True, matcher_options=matcher_options)

        elif token_kind == "begin":
            tok = token_table.def_begin_token(token_label)
            self.begin_token_label = token_label
            # Define dummy handlers for the begin-token, just to catch errors.
            def begin_head(self, lex):
                """Dummy head handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called head-handler for begin token.")
            def begin_tail(self, lex, left):
                """Dummy tail-handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called tail-handler for begin token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, begin_head, token_label)
            self.def_construct(TAIL, begin_tail, token_label, dummy_handler=True)
            self.begin_token_subclass = tok

        elif token_kind == "end":
            tok = token_table.def_end_token(token_label)
            self.end_token_label = token_label
            # Define dummy handlers for the end-token, just to catch errors.
            def end_head(self, lex):
                """Dummy head handler for end-tokens."""
                raise CalledEndTokenHandler("Called head-handler for end token.")
            def end_tail(self, lex, left):
                """Dummy tail-handler for end-tokens."""
                raise CalledEndTokenHandler("Called tail-handler for end token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, end_head, token_label)
            self.def_construct(TAIL, end_tail, token_label, dummy_handler=True)
            self.end_token_subclass = tok

        elif token_kind == "jop":
            if self.jop_token_subclass:
                raise ParserException("A jop token is already defined.  It must be "
                                      "undefined before defining a new one.")
            self.jop_token_label = token_label
            self.jop_ignored_token_label = ignored_token_label
            tok = token_table.def_token(token_label, None)
            self.jop_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        elif token_kind == "null-string":
            if self.null_string_token_subclass:
                raise ParserException("A null-string token is already defined.  It"
                         " must be undefined before defining an new one.")
            self.null_string_token_label = token_label
            tok = token_table.def_token(token_label, None)
            self.null_string_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        else:
            raise ParserException("Bad call to def_token_master, with unrecognized"
                    ' string "{0}" for the keyword argument token_kind.'
                    .format(token_kind))

        tok.token_kind = token_kind
        tok.is_head = False # Set true in recursive_parse if instance parses as a head.
        return tok

    def def_token(self, token_label, regex_string, on_ties=0, ignore=False,
                  matcher_options=None):
        """Define a token.  Use this instead of the Lexer `def_token` method,
        since it adds extra attributes to the tokens."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore,
                              token_kind="regular", matcher_options=matcher_options)

    def def_ignored_token(self, token_label, regex_string, on_ties=0,
                          matcher_options=None):
        """A convenience function to define a token with `ignored=True`."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore=True,
                              token_kind="ignored", matcher_options=matcher_options)

    def def_begin_end_tokens(self, begin_token_label="k_begin",
                                   end_token_label="k_end"):
        """Calls the `Lexer` method to define begin- and end-tokens.  The
        subclasses are then given initial head and tail functions for use in
        the Pratt parser.  To use the `PrattParser` this method must be called,
        not the method of `Lexer` with the same name (since it also creates
        head and tail handler functions that raise exceptions for better error
        messages).  The default is to call this method automatically on
        initialization, with the default token labels for the begin and end
        tokens.  If the flag `default_begin_end_tokens` is set false on
        `PrattParser` initalization then the user must call this function
        (setting whatever token labels are desired).  Returns a tuple
        containing the new begin and end `TokenNode` subclasses."""
        begin_tok = self.def_token_master(begin_token_label, token_kind="begin")
        end_tok = self.def_token_master(end_token_label, token_kind="end")
        return begin_tok, end_tok

    def def_jop_token(self, jop_token_label, ignored_token_label):
        """Define a token for the juxtaposition operator.  This token has no
        regex pattern.  An instance is inserted in `recursive_parse` when it is
        inferred to be present.  This method must be explicitly called before a
        juxtaposition operator can be used (i.e., before `def_jop`).  The
        parameter `jop_token_label` is the label for the newly-created token
        representing the juxtaposition operator.  The `ignored_token_label`
        parameter is the label of an ignored token which must be present for a
        jop to be inferred.  Some already-defined token is required; usually it
        will be a token for spaces and tabs.  If set to `None` then no ignored
        space at all is required (i.e., the operands can be right next to each
        other)."""
        return self.def_token_master(jop_token_label,
                                     ignored_token_label=ignored_token_label,
                                     token_kind="jop")

    def def_null_string_token(self, null_string_token_label="k_null-string"):
        """Define the null-string token.  This token has no regex pattern.  An
        instance is inserted in `recursive_parse` when it is inferred to be
        present based.  This method must be called before a
        null-string can be used.  The parameter `null_string_token_label` is
        the label for the newly-created tok representing it."""
        return self.def_token_master(null_string_token_label,
                                     token_kind="null-string")

    def get_token(self, token_label):
        """Return the token with the label `token_label`.  The reverse
        operation, getting a label from a token instance, can be done by
        looking at the `token_label` attribute of the token."""
        return self.token_table[token_label]

    #
    # Undefine tokens.
    #

    def undef_token(self, token_label):
        """A method for undefining any token defined by the `PrattParser` methods.
        Since the `token_kind` was set for all tokens when they were defined
        it knows how to undelete any kind of token."""
        # TODO: Make sure this is up-to-date with the what the token_master class does.
        token_table = self.token_table
        tok = token_table[token_label]
        kind = tok.token_kind
        if kind == "jop":
            token_table.undef_token(self.jop_token_label)
            self.jop_token_subclass = None
            self.jop_token_label = None
            self.jop_ignored_token_label = None
        elif kind == "null-string":
            token_table.undef_token(self.null_string_token_label)
            self.null_string_token_subclass = None
            self.null_string_token_label = None
            self.null_string_ignored_token_label = None
        else:
            token_table.undef_token(token_label)

    #
    # Methods to define and undefine constructs.
    #

    def def_construct(self, head_or_tail, handler_fun, trigger_token_label,
                      prec=0, construct_label=None, precond_fun=None,
                      precond_priority=0, val_type=None, arg_types=None,
                      eval_fun=None, ast_data=None, token_value_key=None,
                      dummy_handler=False):
        """Define a construct and register it with the token with label
        `trigger_token_label`.  A token with that label must already be in the
        token table or an exception will be raised.

        Stores the construct instance in the parser's construct table and also
        return the construct instance.

        The `head_or_tail` argument should be set to either `HEAD` or `TAIL`.
        If `head_or_tail==TAIL` then the operator precedence will be set to
        `prec`.  For a head handler the `prec` value is ignored and effectively
        set to zero.  For a tail handler a `prec` value greater than zero is
        required or else an exception will be raised (unless `dummy_handler` is
        set true).  Similarly, an exception is raised for a non-zero `prec`
        value for a head-handler (the default value).

        The `construct_label` is an optional string value which can result in
        better error messages.

        The `eval_fun` and the `ast_data` arguments are saved in dicts
        associated with the type signature.

        If `token_value_key` is set to a string value then that value will be
        part of the key tuple for saving AST data and evaluation functions.
        This can be used, for example, when overloading a generic identifier
        with different evaluation functions for when the identifier value is
        `sin`, `cos`, etc.  In looking up the AST data and evaluation function
        the parsed token's actual string value (from the program text) is used
        as the key.  If any overload of a particular construct provides a
        `token_value_key` string then all the other overloads for that
        construct must also (for the time being, at least)."""
        # Note that the parser_instance attribute of tokens is not necessarily
        # set yet when this method is called.
        if isinstance(arg_types, str):
            raise ParserException("The arg_types argument to token_subclass must"
                    " be None or an iterable returning type labels (e.g., a list"
                    " or tuple).")

        if head_or_tail == TAIL and prec <= 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a tail hander and a precedence of zero or less."
                    .format(trigger_token_label))
        if head_or_tail == HEAD and prec != 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a head hander and a precedence not equal to zero."
                    .format(trigger_token_label))

        if precond_fun is None:
            precond_fun = DEFAULT_ALWAYS_TRUE_PRECOND_FUN

        if trigger_token_label in self.token_table:
            trigger_token_subclass = self.get_token(trigger_token_label)
        else:
            raise ParserException("In call to def_construct: subclass for"
                    " token labeled '{0}' has not been defined.  Maybe try"
                    " calling def_token first.".format(trigger_token_label))
            # Below line formerly just created a subclass, but that can mask errors!
            #TokenSubclass = self.token_table.create_token_subclass(token_label)

        if not hasattr(trigger_token_subclass, "token_kind"):
            raise ParserException("Token with label '{0}'  must be defined by the"
                                  " parser's def_token method, not the lexer's method."
                                  .format(trigger_token_label))

        # TODO: Precedence is currently saved as a token attribute.  Consider
        # saving it in the construct instead.  See main Sphinx docs, unimplemented
        # generalizations.
        if head_or_tail == TAIL:
            if (trigger_token_subclass.static_prec != 0 and
                    prec != trigger_token_subclass.static_prec):
                raise ParserException("Redefining the precedence of the triggering"
                        " token subclass '{0}' to a new value {1} not equal"
                        " to the previous nonzero value of {2}."
                        " The original precedence will never be used.  To actually"
                        " reset the value, set trigger_token_label.static_prec=0"
                        " explicitly before this call to def_construct.  Currently"
                        " all operators with the same triggering token must have"
                        " the same precedence value, regardless of preconditions."
                        .format(trigger_token_label, prec,
                                trigger_token_subclass.static_prec))
            trigger_token_subclass.static_prec = prec # Ignore prec for heads; will stay 0.

        # Create the type sig object.
        if self.skip_type_checking:
            type_sig = None
        else:
            type_sig = TypeSig(val_type, arg_types)

        # Register the handler funs.
        construct = self.construct_table.register_construct(
                                          head_or_tail=head_or_tail,
                                          trigger_token_subclass=trigger_token_subclass,
                                          handler_fun=handler_fun,
                                          precond_fun=precond_fun,
                                          precond_priority=precond_priority,
                                          construct_label=construct_label,
                                          type_sig=type_sig,
                                          eval_fun=eval_fun,
                                          ast_data=ast_data,
                                          token_value_key=token_value_key)
        return construct

    def undef_construct(self, construct, type_sig=None, token_value_key=None):
        """Undefine a construct.  If `type_sig` is passed a `TypeSig` instance then
        only that overload is deleted.  If `token_value_key` is also defined then
        only that token key is unregistered.  Otherwise the full construct is
        removed from the parser's construct table."""
        # Note users themselves could unregister the overloads if they have the
        # construct instance.
        self.construct_table.unregister_construct(construct, type_sig, token_value_key)

    #
    # Methods dealing with types.
    #

    def def_type(self, type_label):
        """Define a type associated with the name `type_label`."""
        return self.type_table.create_typeobject(type_label)

    def undef_type(self, type_label):
        """Undefine the type associated with the name `type_label`."""
        self.type_table.undef_typeobject(type_label)

    #
    # The main parse routines.
    #

    def parse_from_lexer(self, lexer_to_use, pstate=None):
        """The same as the `parse` method, but a lexer_to_use is already assumed to be
        initialized.  This is ONLY used when one parser instance calls another
        parser instance (implicitly, via the handler functions of its tokens).
        The outer parser calls this routine of the inner, subexpression parser.
        Such a call to another parser would look something like::

            alternate_parser.parse_from_lexer(lexer_to_use)

        where `lexer_to_use` is the lexer_to_use of the outer parser.  This routine
        temporarily swaps the token table for the passed-in lexer_to_use to be the
        token table for this parser (remember that this parser is the inner
        parser when this routine is called)."""
        # Note you do not need to set the type_table, since the tokens always
        # have fixed references to their own parser instance.

        # Set up to read from lexer_to_use, after setting its token table to
        # be the token table for this parser (this is the inner parser).

        # Temporarily change new lexer's token table.
        lexer_to_use_usual_table = lexer_to_use.token_table
        lexer_to_use.set_token_table(self.token_table)

        # Swap the lexer in.
        usual_lexer = self.lex
        self.lex = lexer_to_use # Swap the lexer.

        try:
            parsed_subexpression = self.parse("IGNORED", pstate=pstate,
                                    partial_expressions=True,
                                    skip_lex_setup=True)
        except ParserException:
            print("Error in `parse_from_lexer` method, in call to `parse` method"
                    " using a different parser's lexer for a subexpression.",
                    file=sys.stderr)
            raise
        finally:
            # Restore the temporary lexer's token table.
            lexer_to_use.set_token_table(lexer_to_use_usual_table)
            self.lex = usual_lexer
        return parsed_subexpression

    def parse(self, program, pstate=None, partial_expressions=None,
                                                      skip_lex_setup=False):
        """The main routine for parsing a full program or expression.  Users of
        the class should call this method to perform the parsing operations
        (after defining a grammar, of course).

        Unless there was a parsing failure or `partial_expressions` is true
        then the lexer is left with the end-token as the current token.

        If the `pstate` variable is set then the value will be pushed as the
        initial state on the production rule stack `pstate_stack`.  The stack
        is then cleared after a successful call.  (Set the parser attribute
        directly for more control.)

        The parser's `partial_expressions` attribute will be used unless it is
        overridden by the parameter `partial_expressions` here.  When it is
        true no check is made for the end-token after `recursive_parse` returns
        a value.    The lexer will be left at the last token consumed, so a
        check for the end-token will tell when all the text was consumed.
        Users are responsible for making sure their grammars are suitable for
        this kind of parsing if the option is set.

        If the `skip_lex_setup` parameter is true then the text `program` is
        ignored and lexer setup is skipped.  This is generally ONLY used when
        multiple parsers are parsing from a common text stream, and `parse` is
        called from the method `parse_from_lexer`."""
        if pstate:
            self.pstate_stack = [pstate] # For parsing production rule grammars.
        if partial_expressions is None:
            partial_expressions = self.partial_expressions

        if not skip_lex_setup:
            self.lex.set_text(program)
        begin_tok = self.lex.token # Get the first token to access recursive_parse.
        parse_tree = begin_tok.recursive_parse(0)

        # Finalize type-checking for root when overloading on return types.
        if self.overload_on_ret_types:
            parse_tree.check_types_in_tree_second_pass(root=True)

        # See if we reached the end of the token stream.
        if not self.lex.peek().is_end_token() and not partial_expressions:
            raise IncompleteParseException("Parsing never reached the end of"
                " the text.  Parsing stopped with tokens still in the lexer."
                "  No syntax element was recognized. The last-parsed token had"
                " value '{0}' and label '{1}'.  Parsing stopped before a token"
                " in the lexer with value '{2}' and label '{3}'.  The partial"
                " result returned is:\n{4}"
                .format(self.lex.token.value, self.lex.token.token_label,
                        self.lex.peek().value, self.lex.peek().token_label,
                        parse_tree.tree_repr()))

        if pstate:
            self.pstate_stack = []
        return parse_tree

#
# Copy the convenience functions from builtin_parse_methods to the PrattParser class.
#

for method in builtin_parse_methods.parse_methods:
    setattr(PrattParser, method.__name__, method)

for method in predefined_token_sets.token_defining_methods:
    setattr(PrattParser, method.__name__, method)

#
# Exceptions
#

class IncompleteParseException(ParserException):
    """Only raised at the end of the `PrattParser` function `parse` if tokens
    remain in the lexer after the parser finishes its parsing."""
    pass

class TokenSubclassMeta(type):
    """A trivial metaclass that will actually create the `TokenSubclass`
    objects.  Since tokens are represented by classes, rather than instances,
    this is necessary in order to change their `__repr__` (the defalt one is
    ugly for tokens) and to overload operators to work for token operands
    in the EBNF-like grammar."""
    def __new__(mcs, name, bases, dct):
        new_class = super(TokenSubclassMeta, mcs).__new__(mcs, name, bases, dct)

        # Below is ugly, but avoids mutual import problems.  Used as an easy
        # way to define token addition so that it works in the grammars defined
        # by the ebnf_classes_and_operators module.
        from .ebnf_classes_and_operators import (
                                     Tok, Not, Prec, nExactly, nOrMore, Repeat)
        # These are saved in a dict below because if they are made attributes
        # then Python 2 complains about "TypeError: unbound method Tok() must
        # be called with TokenClass_k_lpar instance as first argument (got
        # TokenSubclassMeta instance instead)".
        new_class.prod_rule_funs = {
                "Tok": Tok,
                "Not": Not,
                "Prec": Prec,
                "nExactly": nExactly,
                "nOrMore": nOrMore,
                "Repeat": Repeat,
                }
        return new_class

    #
    # Define a nicer-looking __repr__, since the classes represent tokens.
    #

    def __repr__(cls):
        """The representation for tokens.  Tokens are commonly used in the
        code but, being classes, have an ugly default `__repr__` when printed out.
        In this metaclass we can define a better `__repr__` for tokens."""
        string = "TokenClass_{0}".format(cls.token_label)
        return string

    #
    # These overloads work with the ebnf_classes_and_operators module.
    #

    # TODO: Could have a flag to turn overloads on and off, maybe.
    # Might want to turn off when not processing a grammar expression
    # using the tokens, but it really shouldn't matter much.
    def __add__(cls, other):
        """Addition of two tokens is defined to simply return a tuple of
        both tokens.  This is so raw tokens can be used in the operator
        overloaded form of defining production rules for a grammar."""
        return cls.prod_rule_funs["Tok"](cls) + other

    def __radd__(cls, left_other):
        """The right version of `__add__` above."""
        return left_other + cls.prod_rule_funs["Tok"](cls)

    def __or__(cls, other):
        """The `|` symbol simply converts this object into an `ItemList`
        and then calls `__or__` for those objects."""
        return cls.prod_rule_funs["Tok"](cls) | other

    def __ror__(cls, left_other):
        """The right version of `__or__` above."""
        return left_other | cls.prod_rule_funs["Tok"](cls)

    def __rmul__(cls, left_other):
        """The expression `n*token` for an int `n` is "n occurrences of"
        `token`."""
        return cls.prod_rule_funs["Repeat"](left_other, cls)

    def __rpow__(cls, left_other):
        """The expression `n**token` for an int `n` is "n or more occurrences of"
        `token`."""
        return cls.prod_rule_funs["nOrMore"](left_other, cls)

    def __invert__(cls):
        """Define the `~` operator for production rule grammars."""
        return cls.prod_rule_funs["Not"](cls)

    def __getitem__(cls, arg):
        """Define the bracket indexing operator for production rule grammars
        to set the precedence."""
        return cls.prod_rule_funs["Prec"](cls, arg)

def token_subclass_factory():
    """This function is called from the `create_token_subclass` method of
    `TokenTable` when it needs to create a new subclass to begin
    with.  It should not be called directly.

    Create and return a new token subclass which will be modified and used
    to represent a particular kind of token.  Specifically, each scanned token
    matching the regex defined for tokens with a given token label is
    represented as an instance of the subclass created by calling this function
    (with further attributes, such as the token label, added to it).

    Using a separate subclass for each token label allows for attributes
    specific to a kind of token (including head and tail handler methods) to
    later be added to the class itself without conflicts.  This function
    returns a bare-bones subclass without any head or tail functions, etc."""

    class TokenSubclass(TokenSubclassMeta("TokenSubclass", (object,), {}), TokenNode):
    #class TokenSubclass(TokenNode, metaclass=TokenSubclassMeta):  # Python 3
    #class TokenSubclass(TokenNode):                               # No metaclass.
        """The factory function returns this class to represent tokens.  It is a
        subclass of the `TokenNode` class, defined in the lexer module."""
        static_prec = 0 # The prec value for this kind of token, with default zero.
        token_label = None # Set to the actual value later, by create_token_subclass.
        #parser_instance = None # Set by recursive_parse. AVOID if not needed.

        def __init__(self, value):
            """Initialize an instance of the subclass for a token of the kind
            labeled with `token_label`.  The `value` is the actual parsed
            string from the text.  This instance represents the token."""
            super(TokenSubclass, self).__init__() # Call base class __init__.
            self.value = value # Set from lex.token_generator; static value=None.

            # The `expanded_formal_sig` attr is set upon parsing.  It is the
            # expanded form of one of the formal sigs which were registered
            # with the token (the expansion handles wildcards, repeat options,
            # etc.)  It is the signature which matched the actual args.  The
            # `self.expanded_formal_sig` has an attribute `original_formal_sig`
            # which is the original, unexpanded formal signature that matched
            # (after expansion) the actual arguments.  After parsing it is set
            # as the token attribute `original_formal_sig`.  This is important
            # because the `eval_fun` and `ast_data` for tokens are saved in
            # dicts keyed by the original signature at the time when they are
            # defined (via `modify_token`).  So we need the resolved original
            # signature to look up the value.  (Note that if overloading on
            # return types is turned off then these dicts are keyed only on the
            # argument portion of the original typesig.)
            self.original_formal_sig = "Unresolved" # The matching orig sig.
            self.expanded_formal_sig = "Unresolved" # Expanded version of above.
            self.actual_sig = "Unresolved" # The actual signature.

        @classmethod
        def prec(cls):
            """Return the precedence for the token.  This is currently a static
            value for each type of token.  Later it may be dynamic value
            associated with the particular tail function which is selected in a
            given context. Update: may become an attribute of a construct and
            no longer of a token."""
            return cls.static_prec

        def process_not_in_tree(self):
            """Removes any immediate children which have `not_in_tree` set."""
            modified_children = []
            for child in self.children:
                if not hasattr(child, "not_in_tree"):
                    modified_children.append(child)
                else:
                    modified_children += child.children
            self.children = modified_children

        def process_and_check_node(self, construct,
                                   val_type_override=None, all_vals_override=None,
                                   typesig_override=None):
            """This routine is automatically called just after a handler
            function returns a subtree.  It is called for the root of the
            returned subtree.  It sets some attributes and checks that the
            actual types match some defined type signature for the function.

            If `val_type_override` is set to a `TypeObject` instance then the
            return type of both the `expanded_formal_sig` and the `actual_sig`
            for the node is set to that type *after* the first pass of
            processing and type-checking for the subtree is finished.  (This
            option does not currently work for two-pass checking when
            overloading on return types is used.)  This option is useful for
            handling things like parentheses and brackets which inherit the
            type of their child (assuming the parens and brackets are kept as
            nodes in the parse tree and not eliminated).  The override value is
            used for type-checking farther up the expression tree.

            If `all_vals_override` is set to a `TypeObject` instance then all
            the possible signatures have their `val_type` changed to that type
            *before* any checking is done.  This should work for both one and
            two-pass checking, but no check is made for producing duplicate
            types due to the `val_type` changes.

            The `typesig_override` argument must be a `TypeSig` instance.  If
            set it will be *assigned* to the node as its only possible
            `expanded_formal_sig` before type checking (instead of looking up
            the registered ones).  Type checking then proceeds as usual."""

            # Get all the sigs registered for the node's construct.
            if typesig_override is not None:
                all_possible_sigs = [typesig_override]
            else:
                all_possible_sigs = construct.original_sigs
            if all_vals_override:
                all_possible_sigs = [TypeSig(all_vals_override, s.arg_types)
                                                      for s in all_possible_sigs]
            self.all_possible_sigs = all_possible_sigs # Temporary attribute.

            # Do the actual checking.
            if not self.parser_instance.overload_on_ret_types: # One-pass.
                self._check_types_one_pass()
            else: # Two-pass.
                self._check_types_first_of_two_passes()
                # If we have a *unique* matching sig, run pass two on the
                # subtree.  In this case, since the signature is fixed by
                # argument types (regardless of where the top-down pass
                # starts from) we can in this case resolve the types in the
                # subtree early.  Note `check_types_in_tree_second_pass` is
                # also called on the root node from the `parse` method.
                if len(self.matching_sigs) == 1: # matching_sigs set by _check_types
                    self.check_types_in_tree_second_pass()

            # Implement val_type override if set.
            if val_type_override:
                # Note that the original_formal_sig attribute was already set.
                # The ast_data and eval_fun are keyed on that.
                self.expanded_formal_sig = TypeSig(val_type_override,
                                                   self.expanded_formal_sig.arg_types)
                self.actual_sig = TypeSig(val_type_override, self.actual_sig.arg_types)

        def _check_types_one_pass(self):
            """Utility function called from `process_and_check_node` to check
            the actual types against their signatures when overloading is only on
            argument types."""
            all_possible_sigs = self.all_possible_sigs

            # One-pass, each child c has a unique c.expanded_formal_sig already set.
            list_of_child_sig_lists = [[c.expanded_formal_sig] for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)
            # Below all_possible_sigs is saved ONLY for printing error messages.
            self.all_possible_sigs = all_possible_sigs

            # No overloading on return types so we can finalize the actual types.
            if len(self.matching_sigs) != 1:
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution: The actual argument types match"
                        " multiple signatures.")

            # Found a unique signature; set the node's expanded_formal_sig attribute.
            # Saved sig used for eval_fun resolution, ast_data, semantic action, etc.
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type,
                                      [c.actual_sig.val_type for c in self.children])

            # Delete some temporary attributes no longer needed.
            delattr(self, "matching_sigs")
            delattr(self, "all_possible_sigs")

        def _check_types_first_of_two_passes(self):
            """Utility function called from `process_and_check_node` to do the
            first pass in checking the actual types against their signatures.
            Two-pass checking is needed for overloading on return types.  First
            pass goes up the tree, second pass goes back down."""
            all_possible_sigs = self.all_possible_sigs

            # First pass case, multiple sigs in child's self.matching_sigs list.
            list_of_child_sig_lists = [c.matching_sigs for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)

        def check_types_in_tree_second_pass(self, root=False):
            """Recursively run the second pass on the token subtree with the
            `self` node as the root.

            This method currently still needs to be explicitly called for the
            root of the final parse tree, from the `PrattParser` method
            `parse`, as well as from the checking routines here to do partial
            checks on subtrees which are already resolvable."""
            unresolved_children = [
                    c for c in self.children if hasattr(c, "matching_sigs")]
            self._check_types_pass_two() # Call first on self to do top-down.
            for child in unresolved_children: # Recurse on unprocessed children.
                child.check_types_in_tree_second_pass()
            # Delete childrens' matching_sigs lists after they are no longer needed.
            # This also acts as an indicator that the node has been resolved.
            for child in unresolved_children:
                delattr(child, "matching_sigs")
            if root:
                # The final pass in _check_types that deletes these attrs doesn't get
                # run on root, so it is explicitly done here when `root` flag is true.
                delattr(self, "matching_sigs")
                delattr(self, "all_possible_sigs")

        def _check_types_pass_two(self):
            """A second pass is only used when overloading on return types is
            allowed.  It is a top-down pass where each node chooses a unique
            final signature for each of its children.  It depends on the
            node attribute `self.matching_sigs` having been set in the first
            pass."""
            # On FIRST pass: on the way *up* the tree (after getting the
            # literal tokens, the leaves of the tree) get all the signature
            # types for a node which match in arguments for *some* possible
            # return-type choice of the children.  Same as the one-pass
            # version, but now sets of possibilities are allowed and state is
            # saved for the second pass to use: the list of matching sigs is
            # temporarily saved with the node in the self.matched_sigs
            # attribute.
            #
            # Summary: first pass, bottom-up, find all sigs that match possible
            # val_types of the node's children, across all arguments.
            #
            # After the first pass the root should have a unique sig; if not
            # there is ambiguity.  (Each node saved a set of sigs that is
            # satisfiable by some realizable choice of child sigs, and parents
            # can force children to assume any of their possible types).
            #
            # On SECOND pass: On the way *down* the tree, parents choose one
            # sig as final for each child and set it in that child's node as
            # the new self.matching_sigs.  This should always be a unique sig;
            # otherwise there is ambibuity.  Recursively called on children.
            #
            # Summary: second pass, top-down, root is unique and parents assign
            # and set the (unique) signature for each of their children.
            #
            # Note that this algorithm works just as well if the second pass is
            # run on each subtree as soon as the subtree root has a unique
            # signature, and the recursion only goes down to subtrees with
            # roots having a unique signature.  This yields partial results and
            # some error conditions sooner, and is what is implemented here.

            if len(self.matching_sigs) != 1: # The root case needs this.
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution (second pass).  Possible type "
                        "assignments for the children/arguments of the token node match"
                        " {0} possible node signatures: {1}.  Uniqueness is required."
                        .format(len(self.matching_sigs), self.matching_sigs))

            # We have a unique signature; set the node's type attributes
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            # Start setting the actual signature; children will fill arg types
            # when resolved.
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type, [])

            # Set the actual_sig arg_type for the parent (appending in sequence with others).
            if self.parent is not None:
                parent_args_so_far = list(self.parent.actual_sig.arg_types)
                parent_args_so_far.append(self.expanded_formal_sig.val_type)
                self.parent.actual_sig = TypeSig(self.parent.actual_sig.val_type,
                                                 parent_args_so_far)

            # Update the matching_sigs attribute for each child (should be singleton).
            for count, child in enumerate(self.children):
                if not hasattr(child, "matching_sigs"):
                    continue # Already resolved.
                matched_sigs = TypeSig.get_child_sigs_matching_return_arg_type(
                                      child, self.expanded_formal_sig.arg_types[count],
                                      child.matching_sigs)
                # From the first pass, we know at least one child sig matches.
                assert len(matched_sigs) != 0 # Debug.
                if len(matched_sigs) > 1:
                    # Recursion could catch this on the next step, but better err msg.
                    child._raise_type_mismatch_error(matched_sigs,
                        "Token node has multiple signatures with return type matching "
                        "type of parent (pass two). Parent expects type '{0}'.  Defined"
                        " signatures are: {1}."
                        .format(self.expanded_formal_sig.val_type, child.matching_sigs))
                child.matching_sigs = matched_sigs
            return

        def _raise_type_mismatch_error(self, matching_sigs, basic_msg):
            """Raise an error, printing a helpful diagnostic message.  Assumes
            that `_check_types` has been called (to set `self.all_possible_sigs`)."""
            # TODO: Will the self.expanded_formal_sig *ever* be resolved when this routine is
            # called?  If not, then it is not very useful and message could be reworded.
            diagnostic = ("  The current token has value '{0}' and label '{1}'.  "
                         " Its expanded formal signature is {2}.  The"
                         " children/arguments have token labels and values of {3} and "
                         "value types {4}.  The list of matching signatures "
                         "is {5}.  The list of possible signatures was {6}"
                         .format(self.value, self.token_label,
                             self.expanded_formal_sig,
                             list(c.summary_repr() for c in self.children),
                             # Note this below can be "Unresolved", better message?
                             list(c.expanded_formal_sig.val_type
                                  if not isinstance(c.expanded_formal_sig, str)
                                  else c.expanded_formal_sig for c in self.children),
                             matching_sigs, self.all_possible_sigs))
            raise TypeErrorInParsedLanguage(basic_msg + diagnostic)

        #
        # Evaluations and semantic actions.
        #

        @property
        def eval_fun(self):
            """Return the evaluation function saved with the winning construct
            dispatched for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_eval_fun(orig_sig, token_value_key=self.value)

        @property
        def ast_data(self):
            """Return the ast data saved with the winning construct dispatched
            for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_ast_data(orig_sig, token_value_key=self.value)

        def eval_subtree(self):
            """Run the saved evaluation function on the token, if one was
            registered with it.  Returns `None` if no evaluation function is found."""
            orig_sig = self.original_formal_sig # Set during parsing.
            eval_fun = self.eval_fun # Property method above.

            # TODO: Consider if returning None is better than raising exception...
            if not eval_fun:
                return None

            # TODO: Consider if special exception should be raised.
            #if not eval_fun:
            #    raise ParserException("An evaluation function is needed for token with "
            #            "value '{0}' and label '{1}' but no defined and matching "
            #            "evaluation function was found in the dict of eval functions.  "
            #            "The resolved original signature is {2} and the resolve expanded"
            #            " signature is {3}.  The resolved construct_label is {4}.  The "
            #            "token's eval_fun_dict is:\n   {5}."
            #            .format(self.value, self.token_label, orig_sig, sig,
            #                    self.construct_label, self.eval_fun_dict))

            return eval_fun(self)

        #
        # The main recursive_parse function.
        #

        def get_jop_token_instance(self, lex, processed_left, extra_data, subexp_prec):
            """Returns an instance of the jop token iff one should be inferred in the
            current context; otherwise returns `None`."""
            # TODO: extra_data arg now holds subexp_prec as field.
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler

            # Not if jop token is undefined for the parser.
            if not parser_instance.jop_token_subclass:
                return None

            # Not if at end of expression.
            if lex.peek().is_end_token():
                return None

            # Not if the ignored token for jop is set but not present.
            if parser_instance.jop_ignored_token_label and (
                          parser_instance.jop_ignored_token_label
                          not in lex.peek().ignored_before_labels()):
                return None

            # Now infer a jop, but only if 1) its prec would satisfy the while loop
            # in `recursive_parse` as an ordinary token, 2) the next token has
            # a head handler defined in the conditions when the jop will need
            # to run its head handler, and 3) the next token similarly has no
            # tail handler in the context.
            if parser_instance.jop_token_subclass.prec() > subexp_prec:
                # Provisionally infer a jop; create a subclass instance for its token.
                #
                # Todo: Maybe for jop and null-string tokens define methods
                # get_jop_token_instance() which gets the token but calls the
                # lexer to dress it up more like a "real" token, with ignored_before
                # and line numbers, etc. (without putting it in the buffer, of course).
                jop_instance = parser_instance.jop_token_subclass(None)
                jop_instance.extra_data = extra_data

                # This is a little inefficient (since it uses a `go_back` call)
                # but we need to be sure that when the tail handler of the jop
                # is called and it reads a token that that token has a head
                # handler defined for it *in that precondition context*.
                # Otherwise, no jop will be inferred.  We also make sure that
                # it has no tail handler in the context, since then it would be
                # a lower-precedence (lower precedence because we broke out of
                # the loop above) infix or postfix operator, and no jop is
                # inferred before another operator).
                curr_token = lex.next()
                try:
                    # Dispatch here WITHOUT CALLING, since calling will consume
                    # another token; also, deeper-level recursions could cause false
                    # results to come up the recursion chain.  We are just testing
                    # what handlers are defined for the token.
                    _peek_head_handler, head_construct = dispatch_handler(
                                                   HEAD, curr_token, lex, extra_data)
                    try: # Found head handler, now make sure it has no tail handler.
                        _peek_tail_handler, tail_construct = dispatch_handler(
                                   TAIL, curr_token, lex, extra_data, processed_left)
                    except NoHandlerFunctionDefined:
                        # This is the only case where an actual token is returned.
                        return jop_instance
                    else:
                        return None
                except NoHandlerFunctionDefined:
                    return None # No precondition matches, assume no jop.
                finally:
                    #delattr(curr_token, "extra_data") # Only needed if pushback below, not go_back.
                    lex.go_back(1)
            else:
                return None

        def dispatch_null_string_handler(self, head_or_tail, lex, subexp_prec,
                                         extra_data, processed_left=None):
            """Check for any possible matching null-string token handlers;
            return the token and the matching handler if one is found.

            Note that the precedence for a null-string token is set to
            `subexpr_prec`, so it would always have activated the while loop if
            it were a real token."""
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            # See if a null-string token is set and a handler matches preconds.
            if not parser_instance.null_string_token_label:
                return None, None, None
            else:
                # TODO: Later don't re-create each time, save one.
                null_string_token = parser_instance.null_string_token_subclass(None)
            null_string_token.extra_data = extra_data

            curr_token = None
            handler_fun = None
            construct = None
            try:
                handler_fun, construct = dispatch_handler(head_or_tail,
                                                          null_string_token,
                                                          lex, extra_data, processed_left)
                curr_token = null_string_token
            except NoHandlerFunctionDefined:
                pass
            return curr_token, handler_fun, construct

        def recursive_parse(self, subexp_prec, only_head=False):
            """Parse a subexpression as defined by token precedences. Return
            the result of the evaluation.  Recursively builds up the final
            result in `processed_left`, which is the tree for the part of the
            full expression to the left of the current token.

            The list `lookbehind` saves all the previously evaluated
            subexpressions at this level of recursion (i.e., at the top level
            in the same subexpression) and passes it to the dispatched tail
            handlers, in case that routine wants to make use of it.  For
            example, the ordinal position of the token in the top level of the
            subexpression can be calculated from the length of `lookbehind`.

            This function is made a method of `TokenSubclass` so that handler
            functions can easily call it by using `tok.recursive_parse`, and
            also so that it can access the lexer without it needing to be
            passed as an argument.  It is basically a static function,
            though.

            The `extra_data` attribute is set for all triggering tokens, and is
            guaranteed to be available for precondition functions and for
            handler functions.  It is set before any dispatches or recursive calls,
            and is deleted from the token after the recursive call.  It is an
            advanced feature which most users will not need."""
            # Note that all the dispatching functions set the `extra_data`
            # attribute of their token before the dispatching is done, but they
            # do not update `extra_data` itself in any way.

            # Note on below code: It is tempting for efficiency to define a jop
            # and null-string token instance, save it, and only use it when
            # necessary (replacing it only when used).  But some things need to
            # be considered.
            #
            # Now that handlers are not with tokens, that is no longer a
            # concern... TODO go ahead and do this.
            #
            # Is there any special attribute or other thing that is assigned on
            # creation which might change?  Either way, you should probably add
            # extra things like line numbers to mimic ordinary tokens. Note
            # that currently you only really pay the creation cost if you
            # actually use the jop or null-string feature, but a lot of dummy
            # instances are created if you do.

            # This err check catches some cases of tokens defined via Lexer, not all.
            if not hasattr(self, "token_kind"):
                raise ParserException("All tokens used in the parser must be"
                        " defined in via parser's methods, not the lexer's.")

            #
            # Initialize, and set some shorter aliases.
            #

            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            lex = self.token_table.lex
            extra_data = ExtraDataTuple(lookbehind=[], constructs=[],
                                        subexp_prec=subexp_prec)

            #
            # Start the actual Pratt parsing recursion.
            #

            curr_token, head_handler, construct = self.dispatch_null_string_handler(
                                                     HEAD, lex, subexp_prec, extra_data)
            if not curr_token: # No null-string token fired, so use normal next() call.
                curr_token = lex.next()
                head_handler, construct = dispatch_handler(
                                                     HEAD, curr_token, lex, extra_data)

            extra_data.constructs.append(construct)

            # TODO: Should the root of processed_left be set for is_head instead, for
            # general case?  Or set "head_trigger_token" to label instead of None?
            # Consider how lookup will work in usual and general cases of arbitrary
            # token as subtree root.
            curr_token.is_head = True # Used to look up eval_fun and ast_data later.

            processed_left = head_handler()

            delattr(curr_token, "extra_data") # Delete after recurse, allow mem cleanup.
            extra_data.lookbehind.append(processed_left)
            extra_data.constructs.append(construct)

            if only_head:
                return processed_left

            while True:

                #
                # The loop below is the main loop in ordinary Pratt parsing.  The
                # Outer loop is ONLY for the special case when a jop is defined.
                #

                # TODO: Consider modification like code below to allow
                # precedences per constuct, which also makes "prec - 1" no
                # longer necessary for right assoc when property is set for the
                # construct itself.  See what performance hit it has, one
                # go_back per subexpression.  Note that jops use a single
                # go_back already when they are defined...
                #
                # The ugly comment-string code below works.  It just pulls the
                # token-dispatching out to before the precedence test.
                # Obviously could then use some cleanup and refactoring, too.
                # Consider possible interactions with jop and null-string
                # tokens, but they don't do a `next` call anyway.  (Is it
                # better to pull out the ns_token dispatch, at least?  In
                # regular code, how to get null-string to appear at end of a
                # subexpression?)
                #
                # Argument it works: This code is doing exactly the same
                # dispatching as it would inside the loop test, but it is doing
                # it before the loop test.  The loop test never modifies
                # anything.  If the test fails the effects of the dispatches
                # are undone.
                """
                while True:
                    #err = None
                    ns_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if ns_token:
                        curr_token = ns_token
                        peek_prec = lex.token.prec()
                        #peek_prec = construct.prec() # Switch to this...
                    else:
                        curr_token = lex.next()
                        try:
                            tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                            lex, extra_data, processed_left)
                            peek_prec = lex.token.prec()
                            #peek_prec = construct.prec() # Switch to this...
                        except NoHandlerFunctionDefined as e:
                            # If no construct at all then can't have tail handler so
                            # prec should be 0.  But if it fails due to a precond,
                            # token itself could still have a prec > 0.  In that case
                            # it will get inside the loop and fail, but it really
                            # shouldn't have gotten inside.
                            #
                            # Only one test changes, and new one is commented out in
                            # the test file under the old one.
                            #err = e
                            peek_prec = -1 # Always fail test and break.
                            #peek_prec = lex.token.prec()

                    #test_assoc = False if err else (peek_prec == subexp_prec and
                    #                                construct.assoc == "right")
                    test_assoc = peek_prec == subexp_prec and construct.assoc == "right"
                    if peek_prec > subexp_prec or test_assoc:
                        #if err: # Error would have been found inside loop, now above.
                        #    raise err # Avoid error msg changing (makes test fail).
                        processed_left = tail_handler()
                        delattr(curr_token, "extra_data")
                        extra_data.lookbehind.append(processed_left)
                        extra_data.constructs.append(construct)
                    else:
                        if not ns_token:
                            lex.go_back(1)
                        break
                """

                while lex.peek().prec() > subexp_prec:

                    curr_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if not curr_token: # No null handler fired off, get regular way.
                        curr_token = lex.next()
                        tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                        lex, extra_data, processed_left)

                    processed_left = tail_handler()
                    delattr(curr_token, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)

                #
                # Broke out of main loop, determine whether or not to infer a jop.
                #

                jop_instance = self.get_jop_token_instance(
                                         lex, processed_left, extra_data, subexp_prec)
                if jop_instance:
                    jop_tail_handler, construct = dispatch_handler(TAIL, jop_instance,
                                                        lex, extra_data, processed_left)
                    processed_left = jop_tail_handler()
                    delattr(jop_instance, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)
                else:
                    break

            return processed_left

        #
        # Copying instances of tokens.
        #

        def __copy__(self):
            """Return a shallow copy of the token."""
            return copy.copy(self)

        #
        # Some representations that apply to the subclasses.
        #

        def summary_repr_with_types(self):
            """A short summary repr of the node, without its children."""
            return ("<" + str(self.token_label) +
                    ",'" + str(self.value) +
                    "'," + str(self.expanded_formal_sig.val_type) + ">")

        def tree_repr_with_types(self, indent=""):
            """Token representation as the root of a parse subtree, with formatting.
            The optional `indent` parameter can be either an indent string or else
            an integer for the number of spaces to indent.  Note that the ordinary
            `tree_repr` method without types is also available, inherited from
            the base node object."""
            try:
                num_indent = int(indent)
            except ValueError:
                pass
            else:
                indent = " " * num_indent
            string = indent + self.summary_repr_with_types() + "\n"
            for c in self.children:
                string += c.tree_repr_with_types(indent=indent+" "*4)
            return string

        def string_repr_with_types(self):
            """A string repr for the tree that includes type information."""
            string = self.summary_repr_with_types()
            if self.children:
                string += "("
                string += ",".join(c.string_repr_with_types() for c in self.children)
                string += ")"
            return string

        @classmethod
        def class_repr(cls):
            """Print out the `TokenSubclass` classes (representing tokens) in a
            nice way.  The default is hard to read."""
            string = "Token({0})".format(cls.token_label)
            return string

    return TokenSubclass # Return from token_subclass_factory function.

#
# Parser
#

def lexer_add_parser_instance_attribute(lexer, token):
    """Passed to lexer to add a `parser_instance` attribute to each token it
    returns.  This attribute is added to instances at the lexer, from its
    current token table, because of the case where parsers call other parsers.
    (It is not added to general token subclasses in `def_token_master` because
    parsers could potentially share token subclasses.)"""
    token.parser_instance = lexer.token_table.parser_instance # From token table.
    return token

# Could also add parser_instance and construct as fields of the extra data tuple.
# Could extra_data also be passed to handler functions?  Nice to have construct
# instance available there, perhaps.  TODO: Consider.
ExtraDataTuple = namedtuple("ExtraHandlerData", ["lookbehind",
                                                 "constructs",
                                                 "subexp_prec"])

class PrattParser(object):
    """A parser object.  Each parser object contains a table of defined tokens,
    a lexer, a table of constructs, and a table of defined types."""
    def __init__(self, max_peek_tokens=None,
                       max_deque_size=None,
                       lexer = None,
                       default_begin_end_tokens=True,
                       type_table = None,
                       skip_type_checking=False,
                       overload_on_arg_types=True,
                       overload_on_ret_types=False,
                       partial_expressions=False,
                       parser_label=None,
                       raise_on_equal_priority_preconds=False):
        """Initialize the parser.

        The `max_peek_tokens` parameter is an optional arbitrary limit on the
        level of peeks allowed in the lexer.  Setting to 1 limits it to a
        single token lookahead.  The default setting `None` gives
        peek-on-demand as far ahead as requested.

        The `max_deque_size` parameter is an optional limit on the size of the
        deque that the lexer keeps for previous tokens, the current token, and
        requested peek tokens.  The default is for it to grow arbitrarily
        (though it is reset on each parse).  Needs to be large enough for the
        max level of peeks required plus the max `go_back` level required.

        If a `Lexer` instance is passed in the parser will use that lexer and
        its token table, otherwise a new lexer is created.  The any other lexer
        options are ignored.

        No default begin and end functions will be set if a lexer is passed in,
        regardless of the value of `default_begin_end_tokens`.  Otherwise,
        default begin and end tokens will be defined unless
        `default_begin_end_tokens` is set false (note that creating them by
        default is the opposite of the default behavior for the lower-level
        Lexer class).

        Setting `skip_type_checking=True` is slightly faster since typing is
        not being used at all.  Note that overloading depends on type-checking
        to resolve the actual types, so this flag implies that the overload
        flags are all false.  The default is false.  It should be possible to
        define types, use them during testing, and then turn checking off ---
        provided overloading is not used to get different evaluation functions
        or AST data elements for different overloads.

        The `overload_on_arg_types` flag specifies whether or not to overload
        on argument types.  The default is true.  Cannot be changed after
        initialization.

        Setting `overload_on_ret_types` also overloads on argument types.  It
        requires an extra walk of the token tree, and implies overloading on
        argument types.  The default is false.  Cannot be changed after
        initialization.

        If `partial_expressions` is set true then no check will be made in the
        `parse` method to see if the parsing consumed up to the end-token in
        the lexer.  Multiple expression text can be parsed by repeatedly
        calling `parse` when this option is true and checking whether the
        lexer's current token is the end-token.

        The `parser_label` is an optional descriptive string for a parser.
        These can be useful in debugging when they appear in error messages,
        especially when working with multiple parser instances.

        If `raise_on_equal_priority_preconds` is true then an exception will be
        raised if two precondition functions are registered with the same
        trigger token in the same head or tail position which have the same
        precondition priority.  The default is false, and the first-defined
        matching precondition function of the same priority will win any
        competition when several are true.  This option can be used to ensure
        at language define-time that there is no definition-order dependence in
        dispatching.  If two such preconditions functions are mutually
        exclusive there is no problem with them having the same priority, but
        this condition cannot be checked by a program.  A small difference can
        be added."""

        if parser_label:
            self.parser_label = parser_label # Set first, for error messages.
        else:
            self.parser_label = None

        ## Type-checking options below; these cannot be changed after initialization.
        if overload_on_ret_types:
            overload_on_arg_types = True # Overload on ret implies overload on args.
        self.skip_type_checking = skip_type_checking # Skip all type checks, faster.
        if not skip_type_checking:
            self.overload_on_arg_types = overload_on_arg_types
            self.overload_on_ret_types = overload_on_ret_types
        else: # Overloading requires type checking.
            self.overload_on_arg_types = False
            self.overload_on_ret_types = False

        # If exceptions are not raised on ties then with non-mutually-exclusive
        # precond functions the first-set one will have precedence when they
        # are both true.  Need to define this before registering any handlers (
        # which is done below in `def_begin_end_tokens`).
        self.raise_on_equal_priority_preconds = raise_on_equal_priority_preconds
        #self.raise_on_equal_priority_preconds = True # DEBUG

        self.construct_table = ConstructTable(parser_instance=self) # Dict of constructs.
        self.default_construct_label_number = 0 # For unique precondition labels.

        if lexer: # Lexer passed in.
            self.lex = lexer
            self.token_table = lexer.token_table
        else: # No Lexer passed in.
            self.token_table = TokenTable(
                                token_subclass_factory_fun=token_subclass_factory)
            self.lex = Lexer(self.token_table,
                             max_peek_tokens=max_peek_tokens,
                             max_deque_size=max_deque_size,
                             default_begin_end_tokens=False)
            # Set the begin and end tokens unless the user specified not to.
            if default_begin_end_tokens:
                self.def_begin_end_tokens() # Use function's defaults.
        self.lex.default_helper_exception = ParserException # Default for match_next, etc.
        # Add mod function to lexer here, works even if they passed in a lexer.
        self.lex.final_mod_function = lexer_add_parser_instance_attribute

        self.token_table.parser_instance = self # Give token table ref to parser.

        if type_table:
            self.type_table = type_table
        else:
            self.type_table = TypeTable(self)

        self.num_lookahead_tokens = max_peek_tokens
        self.jop_token_label = None # Label of the jop token, if any.
        self.jop_token_subclass = None # The actual jop token, if defined.
        self.null_string_token_label = None # Label of the null-string token, if any.
        self.null_string_token_subclass = None # The actual null-string token, if any.

        self.partial_expressions = partial_expressions # Whether to parse multiple expressions.

        self.pstate_stack = [] # Stack of production rules used in grammar parsing.
        self.top_level_production = False # If true, require grammar parses to consume to end.
        self.disable_pstate_processing = False # Set to temporarily disable grammar parsing.

    #
    # Methods defining tokens.
    #

    def def_token_master(self, token_label, regex_string=None, on_ties=0, ignore=False,
                         token_kind="regular", ignored_token_label=None,
                         matcher_options=None):
        """The master method for defining tokens; all the convenience methods
        actually call it.  Allows for factoring out some common code and
        keeping the attributes of all the different kinds of tokens up-to-date.
        This routine calls the underlying lexer's `def_token` to get tokens and
        then adds extra attributes needed by the `PrattParser` class.

        The `token_kind` argument must be one of the following strings:
        `"regular"`, `"ignored"`, `"begin"`, `"end"`, `"jop"`, or
        `"null-string"`.  The `ignored_token_label` is used only when defining
        a jop.

        Tokens can be shared between parsers if all their properties are the
        same.  Note that for now this includes the precedence value for any
        tail handlers (since that is made a token attribute).  Null-string and
        jop tokens are the exception, but they are special in that they are
        never returned by the lexer, only by a particular parser."""
        token_table = self.token_table

        if token_kind == "regular":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=ignore, matcher_options=matcher_options)

        elif token_kind == "ignored":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=True, matcher_options=matcher_options)

        elif token_kind == "begin":
            tok = token_table.def_begin_token(token_label)
            self.begin_token_label = token_label
            # Define dummy handlers for the begin-token, just to catch errors.
            def begin_head(self, lex):
                """Dummy head handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called head-handler for begin token.")
            def begin_tail(self, lex, left):
                """Dummy tail-handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called tail-handler for begin token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, begin_head, token_label)
            self.def_construct(TAIL, begin_tail, token_label, dummy_handler=True)
            self.begin_token_subclass = tok

        elif token_kind == "end":
            tok = token_table.def_end_token(token_label)
            self.end_token_label = token_label
            # Define dummy handlers for the end-token, just to catch errors.
            def end_head(self, lex):
                """Dummy head handler for end-tokens."""
                raise CalledEndTokenHandler("Called head-handler for end token.")
            def end_tail(self, lex, left):
                """Dummy tail-handler for end-tokens."""
                raise CalledEndTokenHandler("Called tail-handler for end token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, end_head, token_label)
            self.def_construct(TAIL, end_tail, token_label, dummy_handler=True)
            self.end_token_subclass = tok

        elif token_kind == "jop":
            if self.jop_token_subclass:
                raise ParserException("A jop token is already defined.  It must be "
                                      "undefined before defining a new one.")
            self.jop_token_label = token_label
            self.jop_ignored_token_label = ignored_token_label
            tok = token_table.def_token(token_label, None)
            self.jop_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        elif token_kind == "null-string":
            if self.null_string_token_subclass:
                raise ParserException("A null-string token is already defined.  It"
                         " must be undefined before defining an new one.")
            self.null_string_token_label = token_label
            tok = token_table.def_token(token_label, None)
            self.null_string_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        else:
            raise ParserException("Bad call to def_token_master, with unrecognized"
                    ' string "{0}" for the keyword argument token_kind.'
                    .format(token_kind))

        tok.token_kind = token_kind
        tok.is_head = False # Set true in recursive_parse if instance parses as a head.
        return tok

    def def_token(self, token_label, regex_string, on_ties=0, ignore=False,
                  matcher_options=None):
        """Define a token.  Use this instead of the Lexer `def_token` method,
        since it adds extra attributes to the tokens."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore,
                              token_kind="regular", matcher_options=matcher_options)

    def def_ignored_token(self, token_label, regex_string, on_ties=0,
                          matcher_options=None):
        """A convenience function to define a token with `ignored=True`."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore=True,
                              token_kind="ignored", matcher_options=matcher_options)

    def def_begin_end_tokens(self, begin_token_label="k_begin",
                                   end_token_label="k_end"):
        """Calls the `Lexer` method to define begin- and end-tokens.  The
        subclasses are then given initial head and tail functions for use in
        the Pratt parser.  To use the `PrattParser` this method must be called,
        not the method of `Lexer` with the same name (since it also creates
        head and tail handler functions that raise exceptions for better error
        messages).  The default is to call this method automatically on
        initialization, with the default token labels for the begin and end
        tokens.  If the flag `default_begin_end_tokens` is set false on
        `PrattParser` initalization then the user must call this function
        (setting whatever token labels are desired).  Returns a tuple
        containing the new begin and end `TokenNode` subclasses."""
        begin_tok = self.def_token_master(begin_token_label, token_kind="begin")
        end_tok = self.def_token_master(end_token_label, token_kind="end")
        return begin_tok, end_tok

    def def_jop_token(self, jop_token_label, ignored_token_label):
        """Define a token for the juxtaposition operator.  This token has no
        regex pattern.  An instance is inserted in `recursive_parse` when it is
        inferred to be present.  This method must be explicitly called before a
        juxtaposition operator can be used (i.e., before `def_jop`).  The
        parameter `jop_token_label` is the label for the newly-created token
        representing the juxtaposition operator.  The `ignored_token_label`
        parameter is the label of an ignored token which must be present for a
        jop to be inferred.  Some already-defined token is required; usually it
        will be a token for spaces and tabs.  If set to `None` then no ignored
        space at all is required (i.e., the operands can be right next to each
        other)."""
        return self.def_token_master(jop_token_label,
                                     ignored_token_label=ignored_token_label,
                                     token_kind="jop")

    def def_null_string_token(self, null_string_token_label="k_null-string"):
        """Define the null-string token.  This token has no regex pattern.  An
        instance is inserted in `recursive_parse` when it is inferred to be
        present based.  This method must be called before a
        null-string can be used.  The parameter `null_string_token_label` is
        the label for the newly-created tok representing it."""
        return self.def_token_master(null_string_token_label,
                                     token_kind="null-string")

    def get_token(self, token_label):
        """Return the token with the label `token_label`.  The reverse
        operation, getting a label from a token instance, can be done by
        looking at the `token_label` attribute of the token."""
        return self.token_table[token_label]

    #
    # Undefine tokens.
    #

    def undef_token(self, token_label):
        """A method for undefining any token defined by the `PrattParser` methods.
        Since the `token_kind` was set for all tokens when they were defined
        it knows how to undelete any kind of token."""
        # TODO: Make sure this is up-to-date with the what the token_master class does.
        token_table = self.token_table
        tok = token_table[token_label]
        kind = tok.token_kind
        if kind == "jop":
            token_table.undef_token(self.jop_token_label)
            self.jop_token_subclass = None
            self.jop_token_label = None
            self.jop_ignored_token_label = None
        elif kind == "null-string":
            token_table.undef_token(self.null_string_token_label)
            self.null_string_token_subclass = None
            self.null_string_token_label = None
            self.null_string_ignored_token_label = None
        else:
            token_table.undef_token(token_label)

    #
    # Methods to define and undefine constructs.
    #

    def def_construct(self, head_or_tail, handler_fun, trigger_token_label,
                      prec=0, construct_label=None, precond_fun=None,
                      precond_priority=0, val_type=None, arg_types=None,
                      eval_fun=None, ast_data=None, token_value_key=None,
                      dummy_handler=False):
        """Define a construct and register it with the token with label
        `trigger_token_label`.  A token with that label must already be in the
        token table or an exception will be raised.

        Stores the construct instance in the parser's construct table and also
        return the construct instance.

        The `head_or_tail` argument should be set to either `HEAD` or `TAIL`.
        If `head_or_tail==TAIL` then the operator precedence will be set to
        `prec`.  For a head handler the `prec` value is ignored and effectively
        set to zero.  For a tail handler a `prec` value greater than zero is
        required or else an exception will be raised (unless `dummy_handler` is
        set true).  Similarly, an exception is raised for a non-zero `prec`
        value for a head-handler (the default value).

        The `construct_label` is an optional string value which can result in
        better error messages.

        The `eval_fun` and the `ast_data` arguments are saved in dicts
        associated with the type signature.

        If `token_value_key` is set to a string value then that value will be
        part of the key tuple for saving AST data and evaluation functions.
        This can be used, for example, when overloading a generic identifier
        with different evaluation functions for when the identifier value is
        `sin`, `cos`, etc.  In looking up the AST data and evaluation function
        the parsed token's actual string value (from the program text) is used
        as the key.  If any overload of a particular construct provides a
        `token_value_key` string then all the other overloads for that
        construct must also (for the time being, at least)."""
        # Note that the parser_instance attribute of tokens is not necessarily
        # set yet when this method is called.
        if isinstance(arg_types, str):
            raise ParserException("The arg_types argument to token_subclass must"
                    " be None or an iterable returning type labels (e.g., a list"
                    " or tuple).")

        if head_or_tail == TAIL and prec <= 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a tail hander and a precedence of zero or less."
                    .format(trigger_token_label))
        if head_or_tail == HEAD and prec != 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a head hander and a precedence not equal to zero."
                    .format(trigger_token_label))

        if precond_fun is None:
            precond_fun = DEFAULT_ALWAYS_TRUE_PRECOND_FUN

        if trigger_token_label in self.token_table:
            trigger_token_subclass = self.get_token(trigger_token_label)
        else:
            raise ParserException("In call to def_construct: subclass for"
                    " token labeled '{0}' has not been defined.  Maybe try"
                    " calling def_token first.".format(trigger_token_label))
            # Below line formerly just created a subclass, but that can mask errors!
            #TokenSubclass = self.token_table.create_token_subclass(token_label)

        if not hasattr(trigger_token_subclass, "token_kind"):
            raise ParserException("Token with label '{0}'  must be defined by the"
                                  " parser's def_token method, not the lexer's method."
                                  .format(trigger_token_label))

        # TODO: Precedence is currently saved as a token attribute.  Consider
        # saving it in the construct instead.  See main Sphinx docs, unimplemented
        # generalizations.
        if head_or_tail == TAIL:
            if (trigger_token_subclass.static_prec != 0 and
                    prec != trigger_token_subclass.static_prec):
                raise ParserException("Redefining the precedence of the triggering"
                        " token subclass '{0}' to a new value {1} not equal"
                        " to the previous nonzero value of {2}."
                        " The original precedence will never be used.  To actually"
                        " reset the value, set trigger_token_label.static_prec=0"
                        " explicitly before this call to def_construct.  Currently"
                        " all operators with the same triggering token must have"
                        " the same precedence value, regardless of preconditions."
                        .format(trigger_token_label, prec,
                                trigger_token_subclass.static_prec))
            trigger_token_subclass.static_prec = prec # Ignore prec for heads; will stay 0.

        # Create the type sig object.
        if self.skip_type_checking:
            type_sig = None
        else:
            type_sig = TypeSig(val_type, arg_types)

        # Register the handler funs.
        construct = self.construct_table.register_construct(
                                          head_or_tail=head_or_tail,
                                          trigger_token_subclass=trigger_token_subclass,
                                          handler_fun=handler_fun,
                                          precond_fun=precond_fun,
                                          precond_priority=precond_priority,
                                          construct_label=construct_label,
                                          type_sig=type_sig,
                                          eval_fun=eval_fun,
                                          ast_data=ast_data,
                                          token_value_key=token_value_key)
        return construct

    def undef_construct(self, construct, type_sig=None, token_value_key=None):
        """Undefine a construct.  If `type_sig` is passed a `TypeSig` instance then
        only that overload is deleted.  If `token_value_key` is also defined then
        only that token key is unregistered.  Otherwise the full construct is
        removed from the parser's construct table."""
        # Note users themselves could unregister the overloads if they have the
        # construct instance.
        self.construct_table.unregister_construct(construct, type_sig, token_value_key)

    #
    # Methods dealing with types.
    #

    def def_type(self, type_label):
        """Define a type associated with the name `type_label`."""
        return self.type_table.create_typeobject(type_label)

    def undef_type(self, type_label):
        """Undefine the type associated with the name `type_label`."""
        self.type_table.undef_typeobject(type_label)

    #
    # The main parse routines.
    #

    def parse_from_lexer(self, lexer_to_use, pstate=None):
        """The same as the `parse` method, but a lexer_to_use is already assumed to be
        initialized.  This is ONLY used when one parser instance calls another
        parser instance (implicitly, via the handler functions of its tokens).
        The outer parser calls this routine of the inner, subexpression parser.
        Such a call to another parser would look something like::

            alternate_parser.parse_from_lexer(lexer_to_use)

        where `lexer_to_use` is the lexer_to_use of the outer parser.  This routine
        temporarily swaps the token table for the passed-in lexer_to_use to be the
        token table for this parser (remember that this parser is the inner
        parser when this routine is called)."""
        # Note you do not need to set the type_table, since the tokens always
        # have fixed references to their own parser instance.

        # Set up to read from lexer_to_use, after setting its token table to
        # be the token table for this parser (this is the inner parser).

        # Temporarily change new lexer's token table.
        lexer_to_use_usual_table = lexer_to_use.token_table
        lexer_to_use.set_token_table(self.token_table)

        # Swap the lexer in.
        usual_lexer = self.lex
        self.lex = lexer_to_use # Swap the lexer.

        try:
            parsed_subexpression = self.parse("IGNORED", pstate=pstate,
                                    partial_expressions=True,
                                    skip_lex_setup=True)
        except ParserException:
            print("Error in `parse_from_lexer` method, in call to `parse` method"
                    " using a different parser's lexer for a subexpression.",
                    file=sys.stderr)
            raise
        finally:
            # Restore the temporary lexer's token table.
            lexer_to_use.set_token_table(lexer_to_use_usual_table)
            self.lex = usual_lexer
        return parsed_subexpression

    def parse(self, program, pstate=None, partial_expressions=None,
                                                      skip_lex_setup=False):
        """The main routine for parsing a full program or expression.  Users of
        the class should call this method to perform the parsing operations
        (after defining a grammar, of course).

        Unless there was a parsing failure or `partial_expressions` is true
        then the lexer is left with the end-token as the current token.

        If the `pstate` variable is set then the value will be pushed as the
        initial state on the production rule stack `pstate_stack`.  The stack
        is then cleared after a successful call.  (Set the parser attribute
        directly for more control.)

        The parser's `partial_expressions` attribute will be used unless it is
        overridden by the parameter `partial_expressions` here.  When it is
        true no check is made for the end-token after `recursive_parse` returns
        a value.    The lexer will be left at the last token consumed, so a
        check for the end-token will tell when all the text was consumed.
        Users are responsible for making sure their grammars are suitable for
        this kind of parsing if the option is set.

        If the `skip_lex_setup` parameter is true then the text `program` is
        ignored and lexer setup is skipped.  This is generally ONLY used when
        multiple parsers are parsing from a common text stream, and `parse` is
        called from the method `parse_from_lexer`."""
        if pstate:
            self.pstate_stack = [pstate] # For parsing production rule grammars.
        if partial_expressions is None:
            partial_expressions = self.partial_expressions

        if not skip_lex_setup:
            self.lex.set_text(program)
        begin_tok = self.lex.token # Get the first token to access recursive_parse.
        parse_tree = begin_tok.recursive_parse(0)

        # Finalize type-checking for root when overloading on return types.
        if self.overload_on_ret_types:
            parse_tree.check_types_in_tree_second_pass(root=True)

        # See if we reached the end of the token stream.
        if not self.lex.peek().is_end_token() and not partial_expressions:
            raise IncompleteParseException("Parsing never reached the end of"
                " the text.  Parsing stopped with tokens still in the lexer."
                "  No syntax element was recognized. The last-parsed token had"
                " value '{0}' and label '{1}'.  Parsing stopped before a token"
                " in the lexer with value '{2}' and label '{3}'.  The partial"
                " result returned is:\n{4}"
                .format(self.lex.token.value, self.lex.token.token_label,
                        self.lex.peek().value, self.lex.peek().token_label,
                        parse_tree.tree_repr()))

        if pstate:
            self.pstate_stack = []
        return parse_tree

#
# Copy the convenience functions from builtin_parse_methods to the PrattParser class.
#

for method in builtin_parse_methods.parse_methods:
    setattr(PrattParser, method.__name__, method)

for method in predefined_token_sets.token_defining_methods:
    setattr(PrattParser, method.__name__, method)

#
# Exceptions
#

class IncompleteParseException(ParserException):
    """Only raised at the end of the `PrattParser` function `parse` if tokens
    remain in the lexer after the parser finishes its parsing."""
    pass

class TokenSubclassMeta(type):
    """A trivial metaclass that will actually create the `TokenSubclass`
    objects.  Since tokens are represented by classes, rather than instances,
    this is necessary in order to change their `__repr__` (the defalt one is
    ugly for tokens) and to overload operators to work for token operands
    in the EBNF-like grammar."""
    def __new__(mcs, name, bases, dct):
        new_class = super(TokenSubclassMeta, mcs).__new__(mcs, name, bases, dct)

        # Below is ugly, but avoids mutual import problems.  Used as an easy
        # way to define token addition so that it works in the grammars defined
        # by the ebnf_classes_and_operators module.
        from .ebnf_classes_and_operators import (
                                     Tok, Not, Prec, nExactly, nOrMore, Repeat)
        # These are saved in a dict below because if they are made attributes
        # then Python 2 complains about "TypeError: unbound method Tok() must
        # be called with TokenClass_k_lpar instance as first argument (got
        # TokenSubclassMeta instance instead)".
        new_class.prod_rule_funs = {
                "Tok": Tok,
                "Not": Not,
                "Prec": Prec,
                "nExactly": nExactly,
                "nOrMore": nOrMore,
                "Repeat": Repeat,
                }
        return new_class

    #
    # Define a nicer-looking __repr__, since the classes represent tokens.
    #

    def __repr__(cls):
        """The representation for tokens.  Tokens are commonly used in the
        code but, being classes, have an ugly default `__repr__` when printed out.
        In this metaclass we can define a better `__repr__` for tokens."""
        string = "TokenClass_{0}".format(cls.token_label)
        return string

    #
    # These overloads work with the ebnf_classes_and_operators module.
    #

    # TODO: Could have a flag to turn overloads on and off, maybe.
    # Might want to turn off when not processing a grammar expression
    # using the tokens, but it really shouldn't matter much.
    def __add__(cls, other):
        """Addition of two tokens is defined to simply return a tuple of
        both tokens.  This is so raw tokens can be used in the operator
        overloaded form of defining production rules for a grammar."""
        return cls.prod_rule_funs["Tok"](cls) + other

    def __radd__(cls, left_other):
        """The right version of `__add__` above."""
        return left_other + cls.prod_rule_funs["Tok"](cls)

    def __or__(cls, other):
        """The `|` symbol simply converts this object into an `ItemList`
        and then calls `__or__` for those objects."""
        return cls.prod_rule_funs["Tok"](cls) | other

    def __ror__(cls, left_other):
        """The right version of `__or__` above."""
        return left_other | cls.prod_rule_funs["Tok"](cls)

    def __rmul__(cls, left_other):
        """The expression `n*token` for an int `n` is "n occurrences of"
        `token`."""
        return cls.prod_rule_funs["Repeat"](left_other, cls)

    def __rpow__(cls, left_other):
        """The expression `n**token` for an int `n` is "n or more occurrences of"
        `token`."""
        return cls.prod_rule_funs["nOrMore"](left_other, cls)

    def __invert__(cls):
        """Define the `~` operator for production rule grammars."""
        return cls.prod_rule_funs["Not"](cls)

    def __getitem__(cls, arg):
        """Define the bracket indexing operator for production rule grammars
        to set the precedence."""
        return cls.prod_rule_funs["Prec"](cls, arg)

def token_subclass_factory():
    """This function is called from the `create_token_subclass` method of
    `TokenTable` when it needs to create a new subclass to begin
    with.  It should not be called directly.

    Create and return a new token subclass which will be modified and used
    to represent a particular kind of token.  Specifically, each scanned token
    matching the regex defined for tokens with a given token label is
    represented as an instance of the subclass created by calling this function
    (with further attributes, such as the token label, added to it).

    Using a separate subclass for each token label allows for attributes
    specific to a kind of token (including head and tail handler methods) to
    later be added to the class itself without conflicts.  This function
    returns a bare-bones subclass without any head or tail functions, etc."""

    class TokenSubclass(TokenSubclassMeta("TokenSubclass", (object,), {}), TokenNode):
    #class TokenSubclass(TokenNode, metaclass=TokenSubclassMeta):  # Python 3
    #class TokenSubclass(TokenNode):                               # No metaclass.
        """The factory function returns this class to represent tokens.  It is a
        subclass of the `TokenNode` class, defined in the lexer module."""
        static_prec = 0 # The prec value for this kind of token, with default zero.
        token_label = None # Set to the actual value later, by create_token_subclass.
        #parser_instance = None # Set by recursive_parse. AVOID if not needed.

        def __init__(self, value):
            """Initialize an instance of the subclass for a token of the kind
            labeled with `token_label`.  The `value` is the actual parsed
            string from the text.  This instance represents the token."""
            super(TokenSubclass, self).__init__() # Call base class __init__.
            self.value = value # Set from lex.token_generator; static value=None.

            # The `expanded_formal_sig` attr is set upon parsing.  It is the
            # expanded form of one of the formal sigs which were registered
            # with the token (the expansion handles wildcards, repeat options,
            # etc.)  It is the signature which matched the actual args.  The
            # `self.expanded_formal_sig` has an attribute `original_formal_sig`
            # which is the original, unexpanded formal signature that matched
            # (after expansion) the actual arguments.  After parsing it is set
            # as the token attribute `original_formal_sig`.  This is important
            # because the `eval_fun` and `ast_data` for tokens are saved in
            # dicts keyed by the original signature at the time when they are
            # defined (via `modify_token`).  So we need the resolved original
            # signature to look up the value.  (Note that if overloading on
            # return types is turned off then these dicts are keyed only on the
            # argument portion of the original typesig.)
            self.original_formal_sig = "Unresolved" # The matching orig sig.
            self.expanded_formal_sig = "Unresolved" # Expanded version of above.
            self.actual_sig = "Unresolved" # The actual signature.

        @classmethod
        def prec(cls):
            """Return the precedence for the token.  This is currently a static
            value for each type of token.  Later it may be dynamic value
            associated with the particular tail function which is selected in a
            given context. Update: may become an attribute of a construct and
            no longer of a token."""
            return cls.static_prec

        def process_not_in_tree(self):
            """Removes any immediate children which have `not_in_tree` set."""
            modified_children = []
            for child in self.children:
                if not hasattr(child, "not_in_tree"):
                    modified_children.append(child)
                else:
                    modified_children += child.children
            self.children = modified_children

        def process_and_check_node(self, construct,
                                   val_type_override=None, all_vals_override=None,
                                   typesig_override=None):
            """This routine is automatically called just after a handler
            function returns a subtree.  It is called for the root of the
            returned subtree.  It sets some attributes and checks that the
            actual types match some defined type signature for the function.

            If `val_type_override` is set to a `TypeObject` instance then the
            return type of both the `expanded_formal_sig` and the `actual_sig`
            for the node is set to that type *after* the first pass of
            processing and type-checking for the subtree is finished.  (This
            option does not currently work for two-pass checking when
            overloading on return types is used.)  This option is useful for
            handling things like parentheses and brackets which inherit the
            type of their child (assuming the parens and brackets are kept as
            nodes in the parse tree and not eliminated).  The override value is
            used for type-checking farther up the expression tree.

            If `all_vals_override` is set to a `TypeObject` instance then all
            the possible signatures have their `val_type` changed to that type
            *before* any checking is done.  This should work for both one and
            two-pass checking, but no check is made for producing duplicate
            types due to the `val_type` changes.

            The `typesig_override` argument must be a `TypeSig` instance.  If
            set it will be *assigned* to the node as its only possible
            `expanded_formal_sig` before type checking (instead of looking up
            the registered ones).  Type checking then proceeds as usual."""

            # Get all the sigs registered for the node's construct.
            if typesig_override is not None:
                all_possible_sigs = [typesig_override]
            else:
                all_possible_sigs = construct.original_sigs
            if all_vals_override:
                all_possible_sigs = [TypeSig(all_vals_override, s.arg_types)
                                                      for s in all_possible_sigs]
            self.all_possible_sigs = all_possible_sigs # Temporary attribute.

            # Do the actual checking.
            if not self.parser_instance.overload_on_ret_types: # One-pass.
                self._check_types_one_pass()
            else: # Two-pass.
                self._check_types_first_of_two_passes()
                # If we have a *unique* matching sig, run pass two on the
                # subtree.  In this case, since the signature is fixed by
                # argument types (regardless of where the top-down pass
                # starts from) we can in this case resolve the types in the
                # subtree early.  Note `check_types_in_tree_second_pass` is
                # also called on the root node from the `parse` method.
                if len(self.matching_sigs) == 1: # matching_sigs set by _check_types
                    self.check_types_in_tree_second_pass()

            # Implement val_type override if set.
            if val_type_override:
                # Note that the original_formal_sig attribute was already set.
                # The ast_data and eval_fun are keyed on that.
                self.expanded_formal_sig = TypeSig(val_type_override,
                                                   self.expanded_formal_sig.arg_types)
                self.actual_sig = TypeSig(val_type_override, self.actual_sig.arg_types)

        def _check_types_one_pass(self):
            """Utility function called from `process_and_check_node` to check
            the actual types against their signatures when overloading is only on
            argument types."""
            all_possible_sigs = self.all_possible_sigs

            # One-pass, each child c has a unique c.expanded_formal_sig already set.
            list_of_child_sig_lists = [[c.expanded_formal_sig] for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)
            # Below all_possible_sigs is saved ONLY for printing error messages.
            self.all_possible_sigs = all_possible_sigs

            # No overloading on return types so we can finalize the actual types.
            if len(self.matching_sigs) != 1:
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution: The actual argument types match"
                        " multiple signatures.")

            # Found a unique signature; set the node's expanded_formal_sig attribute.
            # Saved sig used for eval_fun resolution, ast_data, semantic action, etc.
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type,
                                      [c.actual_sig.val_type for c in self.children])

            # Delete some temporary attributes no longer needed.
            delattr(self, "matching_sigs")
            delattr(self, "all_possible_sigs")

        def _check_types_first_of_two_passes(self):
            """Utility function called from `process_and_check_node` to do the
            first pass in checking the actual types against their signatures.
            Two-pass checking is needed for overloading on return types.  First
            pass goes up the tree, second pass goes back down."""
            all_possible_sigs = self.all_possible_sigs

            # First pass case, multiple sigs in child's self.matching_sigs list.
            list_of_child_sig_lists = [c.matching_sigs for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)

        def check_types_in_tree_second_pass(self, root=False):
            """Recursively run the second pass on the token subtree with the
            `self` node as the root.

            This method currently still needs to be explicitly called for the
            root of the final parse tree, from the `PrattParser` method
            `parse`, as well as from the checking routines here to do partial
            checks on subtrees which are already resolvable."""
            unresolved_children = [
                    c for c in self.children if hasattr(c, "matching_sigs")]
            self._check_types_pass_two() # Call first on self to do top-down.
            for child in unresolved_children: # Recurse on unprocessed children.
                child.check_types_in_tree_second_pass()
            # Delete childrens' matching_sigs lists after they are no longer needed.
            # This also acts as an indicator that the node has been resolved.
            for child in unresolved_children:
                delattr(child, "matching_sigs")
            if root:
                # The final pass in _check_types that deletes these attrs doesn't get
                # run on root, so it is explicitly done here when `root` flag is true.
                delattr(self, "matching_sigs")
                delattr(self, "all_possible_sigs")

        def _check_types_pass_two(self):
            """A second pass is only used when overloading on return types is
            allowed.  It is a top-down pass where each node chooses a unique
            final signature for each of its children.  It depends on the
            node attribute `self.matching_sigs` having been set in the first
            pass."""
            # On FIRST pass: on the way *up* the tree (after getting the
            # literal tokens, the leaves of the tree) get all the signature
            # types for a node which match in arguments for *some* possible
            # return-type choice of the children.  Same as the one-pass
            # version, but now sets of possibilities are allowed and state is
            # saved for the second pass to use: the list of matching sigs is
            # temporarily saved with the node in the self.matched_sigs
            # attribute.
            #
            # Summary: first pass, bottom-up, find all sigs that match possible
            # val_types of the node's children, across all arguments.
            #
            # After the first pass the root should have a unique sig; if not
            # there is ambiguity.  (Each node saved a set of sigs that is
            # satisfiable by some realizable choice of child sigs, and parents
            # can force children to assume any of their possible types).
            #
            # On SECOND pass: On the way *down* the tree, parents choose one
            # sig as final for each child and set it in that child's node as
            # the new self.matching_sigs.  This should always be a unique sig;
            # otherwise there is ambibuity.  Recursively called on children.
            #
            # Summary: second pass, top-down, root is unique and parents assign
            # and set the (unique) signature for each of their children.
            #
            # Note that this algorithm works just as well if the second pass is
            # run on each subtree as soon as the subtree root has a unique
            # signature, and the recursion only goes down to subtrees with
            # roots having a unique signature.  This yields partial results and
            # some error conditions sooner, and is what is implemented here.

            if len(self.matching_sigs) != 1: # The root case needs this.
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution (second pass).  Possible type "
                        "assignments for the children/arguments of the token node match"
                        " {0} possible node signatures: {1}.  Uniqueness is required."
                        .format(len(self.matching_sigs), self.matching_sigs))

            # We have a unique signature; set the node's type attributes
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            # Start setting the actual signature; children will fill arg types
            # when resolved.
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type, [])

            # Set the actual_sig arg_type for the parent (appending in sequence with others).
            if self.parent is not None:
                parent_args_so_far = list(self.parent.actual_sig.arg_types)
                parent_args_so_far.append(self.expanded_formal_sig.val_type)
                self.parent.actual_sig = TypeSig(self.parent.actual_sig.val_type,
                                                 parent_args_so_far)

            # Update the matching_sigs attribute for each child (should be singleton).
            for count, child in enumerate(self.children):
                if not hasattr(child, "matching_sigs"):
                    continue # Already resolved.
                matched_sigs = TypeSig.get_child_sigs_matching_return_arg_type(
                                      child, self.expanded_formal_sig.arg_types[count],
                                      child.matching_sigs)
                # From the first pass, we know at least one child sig matches.
                assert len(matched_sigs) != 0 # Debug.
                if len(matched_sigs) > 1:
                    # Recursion could catch this on the next step, but better err msg.
                    child._raise_type_mismatch_error(matched_sigs,
                        "Token node has multiple signatures with return type matching "
                        "type of parent (pass two). Parent expects type '{0}'.  Defined"
                        " signatures are: {1}."
                        .format(self.expanded_formal_sig.val_type, child.matching_sigs))
                child.matching_sigs = matched_sigs
            return

        def _raise_type_mismatch_error(self, matching_sigs, basic_msg):
            """Raise an error, printing a helpful diagnostic message.  Assumes
            that `_check_types` has been called (to set `self.all_possible_sigs`)."""
            # TODO: Will the self.expanded_formal_sig *ever* be resolved when this routine is
            # called?  If not, then it is not very useful and message could be reworded.
            diagnostic = ("  The current token has value '{0}' and label '{1}'.  "
                         " Its expanded formal signature is {2}.  The"
                         " children/arguments have token labels and values of {3} and "
                         "value types {4}.  The list of matching signatures "
                         "is {5}.  The list of possible signatures was {6}"
                         .format(self.value, self.token_label,
                             self.expanded_formal_sig,
                             list(c.summary_repr() for c in self.children),
                             # Note this below can be "Unresolved", better message?
                             list(c.expanded_formal_sig.val_type
                                  if not isinstance(c.expanded_formal_sig, str)
                                  else c.expanded_formal_sig for c in self.children),
                             matching_sigs, self.all_possible_sigs))
            raise TypeErrorInParsedLanguage(basic_msg + diagnostic)

        #
        # Evaluations and semantic actions.
        #

        @property
        def eval_fun(self):
            """Return the evaluation function saved with the winning construct
            dispatched for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_eval_fun(orig_sig, token_value_key=self.value)

        @property
        def ast_data(self):
            """Return the ast data saved with the winning construct dispatched
            for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_ast_data(orig_sig, token_value_key=self.value)

        def eval_subtree(self):
            """Run the saved evaluation function on the token, if one was
            registered with it.  Returns `None` if no evaluation function is found."""
            orig_sig = self.original_formal_sig # Set during parsing.
            eval_fun = self.eval_fun # Property method above.

            # TODO: Consider if returning None is better than raising exception...
            if not eval_fun:
                return None

            # TODO: Consider if special exception should be raised.
            #if not eval_fun:
            #    raise ParserException("An evaluation function is needed for token with "
            #            "value '{0}' and label '{1}' but no defined and matching "
            #            "evaluation function was found in the dict of eval functions.  "
            #            "The resolved original signature is {2} and the resolve expanded"
            #            " signature is {3}.  The resolved construct_label is {4}.  The "
            #            "token's eval_fun_dict is:\n   {5}."
            #            .format(self.value, self.token_label, orig_sig, sig,
            #                    self.construct_label, self.eval_fun_dict))

            return eval_fun(self)

        #
        # The main recursive_parse function.
        #

        def get_jop_token_instance(self, lex, processed_left, extra_data, subexp_prec):
            """Returns an instance of the jop token iff one should be inferred in the
            current context; otherwise returns `None`."""
            # TODO: extra_data arg now holds subexp_prec as field.
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler

            # Not if jop token is undefined for the parser.
            if not parser_instance.jop_token_subclass:
                return None

            # Not if at end of expression.
            if lex.peek().is_end_token():
                return None

            # Not if the ignored token for jop is set but not present.
            if parser_instance.jop_ignored_token_label and (
                          parser_instance.jop_ignored_token_label
                          not in lex.peek().ignored_before_labels()):
                return None

            # Now infer a jop, but only if 1) its prec would satisfy the while loop
            # in `recursive_parse` as an ordinary token, 2) the next token has
            # a head handler defined in the conditions when the jop will need
            # to run its head handler, and 3) the next token similarly has no
            # tail handler in the context.
            if parser_instance.jop_token_subclass.prec() > subexp_prec:
                # Provisionally infer a jop; create a subclass instance for its token.
                #
                # Todo: Maybe for jop and null-string tokens define methods
                # get_jop_token_instance() which gets the token but calls the
                # lexer to dress it up more like a "real" token, with ignored_before
                # and line numbers, etc. (without putting it in the buffer, of course).
                jop_instance = parser_instance.jop_token_subclass(None)
                jop_instance.extra_data = extra_data

                # This is a little inefficient (since it uses a `go_back` call)
                # but we need to be sure that when the tail handler of the jop
                # is called and it reads a token that that token has a head
                # handler defined for it *in that precondition context*.
                # Otherwise, no jop will be inferred.  We also make sure that
                # it has no tail handler in the context, since then it would be
                # a lower-precedence (lower precedence because we broke out of
                # the loop above) infix or postfix operator, and no jop is
                # inferred before another operator).
                curr_token = lex.next()
                try:
                    # Dispatch here WITHOUT CALLING, since calling will consume
                    # another token; also, deeper-level recursions could cause false
                    # results to come up the recursion chain.  We are just testing
                    # what handlers are defined for the token.
                    _peek_head_handler, head_construct = dispatch_handler(
                                                   HEAD, curr_token, lex, extra_data)
                    try: # Found head handler, now make sure it has no tail handler.
                        _peek_tail_handler, tail_construct = dispatch_handler(
                                   TAIL, curr_token, lex, extra_data, processed_left)
                    except NoHandlerFunctionDefined:
                        # This is the only case where an actual token is returned.
                        return jop_instance
                    else:
                        return None
                except NoHandlerFunctionDefined:
                    return None # No precondition matches, assume no jop.
                finally:
                    #delattr(curr_token, "extra_data") # Only needed if pushback below, not go_back.
                    lex.go_back(1)
            else:
                return None

        def dispatch_null_string_handler(self, head_or_tail, lex, subexp_prec,
                                         extra_data, processed_left=None):
            """Check for any possible matching null-string token handlers;
            return the token and the matching handler if one is found.

            Note that the precedence for a null-string token is set to
            `subexpr_prec`, so it would always have activated the while loop if
            it were a real token."""
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            # See if a null-string token is set and a handler matches preconds.
            if not parser_instance.null_string_token_label:
                return None, None, None
            else:
                # TODO: Later don't re-create each time, save one.
                null_string_token = parser_instance.null_string_token_subclass(None)
            null_string_token.extra_data = extra_data

            curr_token = None
            handler_fun = None
            construct = None
            try:
                handler_fun, construct = dispatch_handler(head_or_tail,
                                                          null_string_token,
                                                          lex, extra_data, processed_left)
                curr_token = null_string_token
            except NoHandlerFunctionDefined:
                pass
            return curr_token, handler_fun, construct

        def recursive_parse(self, subexp_prec, only_head=False):
            """Parse a subexpression as defined by token precedences. Return
            the result of the evaluation.  Recursively builds up the final
            result in `processed_left`, which is the tree for the part of the
            full expression to the left of the current token.

            The list `lookbehind` saves all the previously evaluated
            subexpressions at this level of recursion (i.e., at the top level
            in the same subexpression) and passes it to the dispatched tail
            handlers, in case that routine wants to make use of it.  For
            example, the ordinal position of the token in the top level of the
            subexpression can be calculated from the length of `lookbehind`.

            This function is made a method of `TokenSubclass` so that handler
            functions can easily call it by using `tok.recursive_parse`, and
            also so that it can access the lexer without it needing to be
            passed as an argument.  It is basically a static function,
            though.

            The `extra_data` attribute is set for all triggering tokens, and is
            guaranteed to be available for precondition functions and for
            handler functions.  It is set before any dispatches or recursive calls,
            and is deleted from the token after the recursive call.  It is an
            advanced feature which most users will not need."""
            # Note that all the dispatching functions set the `extra_data`
            # attribute of their token before the dispatching is done, but they
            # do not update `extra_data` itself in any way.

            # Note on below code: It is tempting for efficiency to define a jop
            # and null-string token instance, save it, and only use it when
            # necessary (replacing it only when used).  But some things need to
            # be considered.
            #
            # Now that handlers are not with tokens, that is no longer a
            # concern... TODO go ahead and do this.
            #
            # Is there any special attribute or other thing that is assigned on
            # creation which might change?  Either way, you should probably add
            # extra things like line numbers to mimic ordinary tokens. Note
            # that currently you only really pay the creation cost if you
            # actually use the jop or null-string feature, but a lot of dummy
            # instances are created if you do.

            # This err check catches some cases of tokens defined via Lexer, not all.
            if not hasattr(self, "token_kind"):
                raise ParserException("All tokens used in the parser must be"
                        " defined in via parser's methods, not the lexer's.")

            #
            # Initialize, and set some shorter aliases.
            #

            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            lex = self.token_table.lex
            extra_data = ExtraDataTuple(lookbehind=[], constructs=[],
                                        subexp_prec=subexp_prec)

            #
            # Start the actual Pratt parsing recursion.
            #

            curr_token, head_handler, construct = self.dispatch_null_string_handler(
                                                     HEAD, lex, subexp_prec, extra_data)
            if not curr_token: # No null-string token fired, so use normal next() call.
                curr_token = lex.next()
                head_handler, construct = dispatch_handler(
                                                     HEAD, curr_token, lex, extra_data)

            extra_data.constructs.append(construct)

            # TODO: Should the root of processed_left be set for is_head instead, for
            # general case?  Or set "head_trigger_token" to label instead of None?
            # Consider how lookup will work in usual and general cases of arbitrary
            # token as subtree root.
            curr_token.is_head = True # Used to look up eval_fun and ast_data later.

            processed_left = head_handler()

            delattr(curr_token, "extra_data") # Delete after recurse, allow mem cleanup.
            extra_data.lookbehind.append(processed_left)
            extra_data.constructs.append(construct)

            if only_head:
                return processed_left

            while True:

                #
                # The loop below is the main loop in ordinary Pratt parsing.  The
                # Outer loop is ONLY for the special case when a jop is defined.
                #

                # TODO: Consider modification like code below to allow
                # precedences per constuct, which also makes "prec - 1" no
                # longer necessary for right assoc when property is set for the
                # construct itself.  See what performance hit it has, one
                # go_back per subexpression.  Note that jops use a single
                # go_back already when they are defined...
                #
                # The ugly comment-string code below works.  It just pulls the
                # token-dispatching out to before the precedence test.
                # Obviously could then use some cleanup and refactoring, too.
                # Consider possible interactions with jop and null-string
                # tokens, but they don't do a `next` call anyway.  (Is it
                # better to pull out the ns_token dispatch, at least?  In
                # regular code, how to get null-string to appear at end of a
                # subexpression?)
                #
                # Argument it works: This code is doing exactly the same
                # dispatching as it would inside the loop test, but it is doing
                # it before the loop test.  The loop test never modifies
                # anything.  If the test fails the effects of the dispatches
                # are undone.
                """
                while True:
                    #err = None
                    ns_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if ns_token:
                        curr_token = ns_token
                        peek_prec = lex.token.prec()
                        #peek_prec = construct.prec() # Switch to this...
                    else:
                        curr_token = lex.next()
                        try:
                            tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                            lex, extra_data, processed_left)
                            peek_prec = lex.token.prec()
                            #peek_prec = construct.prec() # Switch to this...
                        except NoHandlerFunctionDefined as e:
                            # If no construct at all then can't have tail handler so
                            # prec should be 0.  But if it fails due to a precond,
                            # token itself could still have a prec > 0.  In that case
                            # it will get inside the loop and fail, but it really
                            # shouldn't have gotten inside.
                            #
                            # Only one test changes, and new one is commented out in
                            # the test file under the old one.
                            #err = e
                            peek_prec = -1 # Always fail test and break.
                            #peek_prec = lex.token.prec()

                    #test_assoc = False if err else (peek_prec == subexp_prec and
                    #                                construct.assoc == "right")
                    test_assoc = peek_prec == subexp_prec and construct.assoc == "right"
                    if peek_prec > subexp_prec or test_assoc:
                        #if err: # Error would have been found inside loop, now above.
                        #    raise err # Avoid error msg changing (makes test fail).
                        processed_left = tail_handler()
                        delattr(curr_token, "extra_data")
                        extra_data.lookbehind.append(processed_left)
                        extra_data.constructs.append(construct)
                    else:
                        if not ns_token:
                            lex.go_back(1)
                        break
                """

                while lex.peek().prec() > subexp_prec:

                    curr_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if not curr_token: # No null handler fired off, get regular way.
                        curr_token = lex.next()
                        tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                        lex, extra_data, processed_left)

                    processed_left = tail_handler()
                    delattr(curr_token, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)

                #
                # Broke out of main loop, determine whether or not to infer a jop.
                #

                jop_instance = self.get_jop_token_instance(
                                         lex, processed_left, extra_data, subexp_prec)
                if jop_instance:
                    jop_tail_handler, construct = dispatch_handler(TAIL, jop_instance,
                                                        lex, extra_data, processed_left)
                    processed_left = jop_tail_handler()
                    delattr(jop_instance, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)
                else:
                    break

            return processed_left

        #
        # Copying instances of tokens.
        #

        def __copy__(self):
            """Return a shallow copy of the token."""
            return copy.copy(self)

        #
        # Some representations that apply to the subclasses.
        #

        def summary_repr_with_types(self):
            """A short summary repr of the node, without its children."""
            return ("<" + str(self.token_label) +
                    ",'" + str(self.value) +
                    "'," + str(self.expanded_formal_sig.val_type) + ">")

        def tree_repr_with_types(self, indent=""):
            """Token representation as the root of a parse subtree, with formatting.
            The optional `indent` parameter can be either an indent string or else
            an integer for the number of spaces to indent.  Note that the ordinary
            `tree_repr` method without types is also available, inherited from
            the base node object."""
            try:
                num_indent = int(indent)
            except ValueError:
                pass
            else:
                indent = " " * num_indent
            string = indent + self.summary_repr_with_types() + "\n"
            for c in self.children:
                string += c.tree_repr_with_types(indent=indent+" "*4)
            return string

        def string_repr_with_types(self):
            """A string repr for the tree that includes type information."""
            string = self.summary_repr_with_types()
            if self.children:
                string += "("
                string += ",".join(c.string_repr_with_types() for c in self.children)
                string += ")"
            return string

        @classmethod
        def class_repr(cls):
            """Print out the `TokenSubclass` classes (representing tokens) in a
            nice way.  The default is hard to read."""
            string = "Token({0})".format(cls.token_label)
            return string

    return TokenSubclass # Return from token_subclass_factory function.

#
# Parser
#

def lexer_add_parser_instance_attribute(lexer, token):
    """Passed to lexer to add a `parser_instance` attribute to each token it
    returns.  This attribute is added to instances at the lexer, from its
    current token table, because of the case where parsers call other parsers.
    (It is not added to general token subclasses in `def_token_master` because
    parsers could potentially share token subclasses.)"""
    token.parser_instance = lexer.token_table.parser_instance # From token table.
    return token

# Could also add parser_instance and construct as fields of the extra data tuple.
# Could extra_data also be passed to handler functions?  Nice to have construct
# instance available there, perhaps.  TODO: Consider.
ExtraDataTuple = namedtuple("ExtraHandlerData", ["lookbehind",
                                                 "constructs",
                                                 "subexp_prec"])

class PrattParser(object):
    """A parser object.  Each parser object contains a table of defined tokens,
    a lexer, a table of constructs, and a table of defined types."""
    def __init__(self, max_peek_tokens=None,
                       max_deque_size=None,
                       lexer = None,
                       default_begin_end_tokens=True,
                       type_table = None,
                       skip_type_checking=False,
                       overload_on_arg_types=True,
                       overload_on_ret_types=False,
                       partial_expressions=False,
                       parser_label=None,
                       raise_on_equal_priority_preconds=False):
        """Initialize the parser.

        The `max_peek_tokens` parameter is an optional arbitrary limit on the
        level of peeks allowed in the lexer.  Setting to 1 limits it to a
        single token lookahead.  The default setting `None` gives
        peek-on-demand as far ahead as requested.

        The `max_deque_size` parameter is an optional limit on the size of the
        deque that the lexer keeps for previous tokens, the current token, and
        requested peek tokens.  The default is for it to grow arbitrarily
        (though it is reset on each parse).  Needs to be large enough for the
        max level of peeks required plus the max `go_back` level required.

        If a `Lexer` instance is passed in the parser will use that lexer and
        its token table, otherwise a new lexer is created.  The any other lexer
        options are ignored.

        No default begin and end functions will be set if a lexer is passed in,
        regardless of the value of `default_begin_end_tokens`.  Otherwise,
        default begin and end tokens will be defined unless
        `default_begin_end_tokens` is set false (note that creating them by
        default is the opposite of the default behavior for the lower-level
        Lexer class).

        Setting `skip_type_checking=True` is slightly faster since typing is
        not being used at all.  Note that overloading depends on type-checking
        to resolve the actual types, so this flag implies that the overload
        flags are all false.  The default is false.  It should be possible to
        define types, use them during testing, and then turn checking off ---
        provided overloading is not used to get different evaluation functions
        or AST data elements for different overloads.

        The `overload_on_arg_types` flag specifies whether or not to overload
        on argument types.  The default is true.  Cannot be changed after
        initialization.

        Setting `overload_on_ret_types` also overloads on argument types.  It
        requires an extra walk of the token tree, and implies overloading on
        argument types.  The default is false.  Cannot be changed after
        initialization.

        If `partial_expressions` is set true then no check will be made in the
        `parse` method to see if the parsing consumed up to the end-token in
        the lexer.  Multiple expression text can be parsed by repeatedly
        calling `parse` when this option is true and checking whether the
        lexer's current token is the end-token.

        The `parser_label` is an optional descriptive string for a parser.
        These can be useful in debugging when they appear in error messages,
        especially when working with multiple parser instances.

        If `raise_on_equal_priority_preconds` is true then an exception will be
        raised if two precondition functions are registered with the same
        trigger token in the same head or tail position which have the same
        precondition priority.  The default is false, and the first-defined
        matching precondition function of the same priority will win any
        competition when several are true.  This option can be used to ensure
        at language define-time that there is no definition-order dependence in
        dispatching.  If two such preconditions functions are mutually
        exclusive there is no problem with them having the same priority, but
        this condition cannot be checked by a program.  A small difference can
        be added."""

        if parser_label:
            self.parser_label = parser_label # Set first, for error messages.
        else:
            self.parser_label = None

        ## Type-checking options below; these cannot be changed after initialization.
        if overload_on_ret_types:
            overload_on_arg_types = True # Overload on ret implies overload on args.
        self.skip_type_checking = skip_type_checking # Skip all type checks, faster.
        if not skip_type_checking:
            self.overload_on_arg_types = overload_on_arg_types
            self.overload_on_ret_types = overload_on_ret_types
        else: # Overloading requires type checking.
            self.overload_on_arg_types = False
            self.overload_on_ret_types = False

        # If exceptions are not raised on ties then with non-mutually-exclusive
        # precond functions the first-set one will have precedence when they
        # are both true.  Need to define this before registering any handlers (
        # which is done below in `def_begin_end_tokens`).
        self.raise_on_equal_priority_preconds = raise_on_equal_priority_preconds
        #self.raise_on_equal_priority_preconds = True # DEBUG

        self.construct_table = ConstructTable(parser_instance=self) # Dict of constructs.
        self.default_construct_label_number = 0 # For unique precondition labels.

        if lexer: # Lexer passed in.
            self.lex = lexer
            self.token_table = lexer.token_table
        else: # No Lexer passed in.
            self.token_table = TokenTable(
                                token_subclass_factory_fun=token_subclass_factory)
            self.lex = Lexer(self.token_table,
                             max_peek_tokens=max_peek_tokens,
                             max_deque_size=max_deque_size,
                             default_begin_end_tokens=False)
            # Set the begin and end tokens unless the user specified not to.
            if default_begin_end_tokens:
                self.def_begin_end_tokens() # Use function's defaults.
        self.lex.default_helper_exception = ParserException # Default for match_next, etc.
        # Add mod function to lexer here, works even if they passed in a lexer.
        self.lex.final_mod_function = lexer_add_parser_instance_attribute

        self.token_table.parser_instance = self # Give token table ref to parser.

        if type_table:
            self.type_table = type_table
        else:
            self.type_table = TypeTable(self)

        self.num_lookahead_tokens = max_peek_tokens
        self.jop_token_label = None # Label of the jop token, if any.
        self.jop_token_subclass = None # The actual jop token, if defined.
        self.null_string_token_label = None # Label of the null-string token, if any.
        self.null_string_token_subclass = None # The actual null-string token, if any.

        self.partial_expressions = partial_expressions # Whether to parse multiple expressions.

        self.pstate_stack = [] # Stack of production rules used in grammar parsing.
        self.top_level_production = False # If true, require grammar parses to consume to end.
        self.disable_pstate_processing = False # Set to temporarily disable grammar parsing.

    #
    # Methods defining tokens.
    #

    def def_token_master(self, token_label, regex_string=None, on_ties=0, ignore=False,
                         token_kind="regular", ignored_token_label=None,
                         matcher_options=None):
        """The master method for defining tokens; all the convenience methods
        actually call it.  Allows for factoring out some common code and
        keeping the attributes of all the different kinds of tokens up-to-date.
        This routine calls the underlying lexer's `def_token` to get tokens and
        then adds extra attributes needed by the `PrattParser` class.

        The `token_kind` argument must be one of the following strings:
        `"regular"`, `"ignored"`, `"begin"`, `"end"`, `"jop"`, or
        `"null-string"`.  The `ignored_token_label` is used only when defining
        a jop.

        Tokens can be shared between parsers if all their properties are the
        same.  Note that for now this includes the precedence value for any
        tail handlers (since that is made a token attribute).  Null-string and
        jop tokens are the exception, but they are special in that they are
        never returned by the lexer, only by a particular parser."""
        token_table = self.token_table

        if token_kind == "regular":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=ignore, matcher_options=matcher_options)

        elif token_kind == "ignored":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=True, matcher_options=matcher_options)

        elif token_kind == "begin":
            tok = token_table.def_begin_token(token_label)
            self.begin_token_label = token_label
            # Define dummy handlers for the begin-token, just to catch errors.
            def begin_head(self, lex):
                """Dummy head handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called head-handler for begin token.")
            def begin_tail(self, lex, left):
                """Dummy tail-handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called tail-handler for begin token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, begin_head, token_label)
            self.def_construct(TAIL, begin_tail, token_label, dummy_handler=True)
            self.begin_token_subclass = tok

        elif token_kind == "end":
            tok = token_table.def_end_token(token_label)
            self.end_token_label = token_label
            # Define dummy handlers for the end-token, just to catch errors.
            def end_head(self, lex):
                """Dummy head handler for end-tokens."""
                raise CalledEndTokenHandler("Called head-handler for end token.")
            def end_tail(self, lex, left):
                """Dummy tail-handler for end-tokens."""
                raise CalledEndTokenHandler("Called tail-handler for end token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, end_head, token_label)
            self.def_construct(TAIL, end_tail, token_label, dummy_handler=True)
            self.end_token_subclass = tok

        elif token_kind == "jop":
            if self.jop_token_subclass:
                raise ParserException("A jop token is already defined.  It must be "
                                      "undefined before defining a new one.")
            self.jop_token_label = token_label
            self.jop_ignored_token_label = ignored_token_label
            tok = token_table.def_token(token_label, None)
            self.jop_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        elif token_kind == "null-string":
            if self.null_string_token_subclass:
                raise ParserException("A null-string token is already defined.  It"
                         " must be undefined before defining an new one.")
            self.null_string_token_label = token_label
            tok = token_table.def_token(token_label, None)
            self.null_string_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        else:
            raise ParserException("Bad call to def_token_master, with unrecognized"
                    ' string "{0}" for the keyword argument token_kind.'
                    .format(token_kind))

        tok.token_kind = token_kind
        tok.is_head = False # Set true in recursive_parse if instance parses as a head.
        return tok

    def def_token(self, token_label, regex_string, on_ties=0, ignore=False,
                  matcher_options=None):
        """Define a token.  Use this instead of the Lexer `def_token` method,
        since it adds extra attributes to the tokens."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore,
                              token_kind="regular", matcher_options=matcher_options)

    def def_ignored_token(self, token_label, regex_string, on_ties=0,
                          matcher_options=None):
        """A convenience function to define a token with `ignored=True`."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore=True,
                              token_kind="ignored", matcher_options=matcher_options)

    def def_begin_end_tokens(self, begin_token_label="k_begin",
                                   end_token_label="k_end"):
        """Calls the `Lexer` method to define begin- and end-tokens.  The
        subclasses are then given initial head and tail functions for use in
        the Pratt parser.  To use the `PrattParser` this method must be called,
        not the method of `Lexer` with the same name (since it also creates
        head and tail handler functions that raise exceptions for better error
        messages).  The default is to call this method automatically on
        initialization, with the default token labels for the begin and end
        tokens.  If the flag `default_begin_end_tokens` is set false on
        `PrattParser` initalization then the user must call this function
        (setting whatever token labels are desired).  Returns a tuple
        containing the new begin and end `TokenNode` subclasses."""
        begin_tok = self.def_token_master(begin_token_label, token_kind="begin")
        end_tok = self.def_token_master(end_token_label, token_kind="end")
        return begin_tok, end_tok

    def def_jop_token(self, jop_token_label, ignored_token_label):
        """Define a token for the juxtaposition operator.  This token has no
        regex pattern.  An instance is inserted in `recursive_parse` when it is
        inferred to be present.  This method must be explicitly called before a
        juxtaposition operator can be used (i.e., before `def_jop`).  The
        parameter `jop_token_label` is the label for the newly-created token
        representing the juxtaposition operator.  The `ignored_token_label`
        parameter is the label of an ignored token which must be present for a
        jop to be inferred.  Some already-defined token is required; usually it
        will be a token for spaces and tabs.  If set to `None` then no ignored
        space at all is required (i.e., the operands can be right next to each
        other)."""
        return self.def_token_master(jop_token_label,
                                     ignored_token_label=ignored_token_label,
                                     token_kind="jop")

    def def_null_string_token(self, null_string_token_label="k_null-string"):
        """Define the null-string token.  This token has no regex pattern.  An
        instance is inserted in `recursive_parse` when it is inferred to be
        present based.  This method must be called before a
        null-string can be used.  The parameter `null_string_token_label` is
        the label for the newly-created tok representing it."""
        return self.def_token_master(null_string_token_label,
                                     token_kind="null-string")

    def get_token(self, token_label):
        """Return the token with the label `token_label`.  The reverse
        operation, getting a label from a token instance, can be done by
        looking at the `token_label` attribute of the token."""
        return self.token_table[token_label]

    #
    # Undefine tokens.
    #

    def undef_token(self, token_label):
        """A method for undefining any token defined by the `PrattParser` methods.
        Since the `token_kind` was set for all tokens when they were defined
        it knows how to undelete any kind of token."""
        # TODO: Make sure this is up-to-date with the what the token_master class does.
        token_table = self.token_table
        tok = token_table[token_label]
        kind = tok.token_kind
        if kind == "jop":
            token_table.undef_token(self.jop_token_label)
            self.jop_token_subclass = None
            self.jop_token_label = None
            self.jop_ignored_token_label = None
        elif kind == "null-string":
            token_table.undef_token(self.null_string_token_label)
            self.null_string_token_subclass = None
            self.null_string_token_label = None
            self.null_string_ignored_token_label = None
        else:
            token_table.undef_token(token_label)

    #
    # Methods to define and undefine constructs.
    #

    def def_construct(self, head_or_tail, handler_fun, trigger_token_label,
                      prec=0, construct_label=None, precond_fun=None,
                      precond_priority=0, val_type=None, arg_types=None,
                      eval_fun=None, ast_data=None, token_value_key=None,
                      dummy_handler=False):
        """Define a construct and register it with the token with label
        `trigger_token_label`.  A token with that label must already be in the
        token table or an exception will be raised.

        Stores the construct instance in the parser's construct table and also
        return the construct instance.

        The `head_or_tail` argument should be set to either `HEAD` or `TAIL`.
        If `head_or_tail==TAIL` then the operator precedence will be set to
        `prec`.  For a head handler the `prec` value is ignored and effectively
        set to zero.  For a tail handler a `prec` value greater than zero is
        required or else an exception will be raised (unless `dummy_handler` is
        set true).  Similarly, an exception is raised for a non-zero `prec`
        value for a head-handler (the default value).

        The `construct_label` is an optional string value which can result in
        better error messages.

        The `eval_fun` and the `ast_data` arguments are saved in dicts
        associated with the type signature.

        If `token_value_key` is set to a string value then that value will be
        part of the key tuple for saving AST data and evaluation functions.
        This can be used, for example, when overloading a generic identifier
        with different evaluation functions for when the identifier value is
        `sin`, `cos`, etc.  In looking up the AST data and evaluation function
        the parsed token's actual string value (from the program text) is used
        as the key.  If any overload of a particular construct provides a
        `token_value_key` string then all the other overloads for that
        construct must also (for the time being, at least)."""
        # Note that the parser_instance attribute of tokens is not necessarily
        # set yet when this method is called.
        if isinstance(arg_types, str):
            raise ParserException("The arg_types argument to token_subclass must"
                    " be None or an iterable returning type labels (e.g., a list"
                    " or tuple).")

        if head_or_tail == TAIL and prec <= 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a tail hander and a precedence of zero or less."
                    .format(trigger_token_label))
        if head_or_tail == HEAD and prec != 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a head hander and a precedence not equal to zero."
                    .format(trigger_token_label))

        if precond_fun is None:
            precond_fun = DEFAULT_ALWAYS_TRUE_PRECOND_FUN

        if trigger_token_label in self.token_table:
            trigger_token_subclass = self.get_token(trigger_token_label)
        else:
            raise ParserException("In call to def_construct: subclass for"
                    " token labeled '{0}' has not been defined.  Maybe try"
                    " calling def_token first.".format(trigger_token_label))
            # Below line formerly just created a subclass, but that can mask errors!
            #TokenSubclass = self.token_table.create_token_subclass(token_label)

        if not hasattr(trigger_token_subclass, "token_kind"):
            raise ParserException("Token with label '{0}'  must be defined by the"
                                  " parser's def_token method, not the lexer's method."
                                  .format(trigger_token_label))

        # TODO: Precedence is currently saved as a token attribute.  Consider
        # saving it in the construct instead.  See main Sphinx docs, unimplemented
        # generalizations.
        if head_or_tail == TAIL:
            if (trigger_token_subclass.static_prec != 0 and
                    prec != trigger_token_subclass.static_prec):
                raise ParserException("Redefining the precedence of the triggering"
                        " token subclass '{0}' to a new value {1} not equal"
                        " to the previous nonzero value of {2}."
                        " The original precedence will never be used.  To actually"
                        " reset the value, set trigger_token_label.static_prec=0"
                        " explicitly before this call to def_construct.  Currently"
                        " all operators with the same triggering token must have"
                        " the same precedence value, regardless of preconditions."
                        .format(trigger_token_label, prec,
                                trigger_token_subclass.static_prec))
            trigger_token_subclass.static_prec = prec # Ignore prec for heads; will stay 0.

        # Create the type sig object.
        if self.skip_type_checking:
            type_sig = None
        else:
            type_sig = TypeSig(val_type, arg_types)

        # Register the handler funs.
        construct = self.construct_table.register_construct(
                                          head_or_tail=head_or_tail,
                                          trigger_token_subclass=trigger_token_subclass,
                                          handler_fun=handler_fun,
                                          precond_fun=precond_fun,
                                          precond_priority=precond_priority,
                                          construct_label=construct_label,
                                          type_sig=type_sig,
                                          eval_fun=eval_fun,
                                          ast_data=ast_data,
                                          token_value_key=token_value_key)
        return construct

    def undef_construct(self, construct, type_sig=None, token_value_key=None):
        """Undefine a construct.  If `type_sig` is passed a `TypeSig` instance then
        only that overload is deleted.  If `token_value_key` is also defined then
        only that token key is unregistered.  Otherwise the full construct is
        removed from the parser's construct table."""
        # Note users themselves could unregister the overloads if they have the
        # construct instance.
        self.construct_table.unregister_construct(construct, type_sig, token_value_key)

    #
    # Methods dealing with types.
    #

    def def_type(self, type_label):
        """Define a type associated with the name `type_label`."""
        return self.type_table.create_typeobject(type_label)

    def undef_type(self, type_label):
        """Undefine the type associated with the name `type_label`."""
        self.type_table.undef_typeobject(type_label)

    #
    # The main parse routines.
    #

    def parse_from_lexer(self, lexer_to_use, pstate=None):
        """The same as the `parse` method, but a lexer_to_use is already assumed to be
        initialized.  This is ONLY used when one parser instance calls another
        parser instance (implicitly, via the handler functions of its tokens).
        The outer parser calls this routine of the inner, subexpression parser.
        Such a call to another parser would look something like::

            alternate_parser.parse_from_lexer(lexer_to_use)

        where `lexer_to_use` is the lexer_to_use of the outer parser.  This routine
        temporarily swaps the token table for the passed-in lexer_to_use to be the
        token table for this parser (remember that this parser is the inner
        parser when this routine is called)."""
        # Note you do not need to set the type_table, since the tokens always
        # have fixed references to their own parser instance.

        # Set up to read from lexer_to_use, after setting its token table to
        # be the token table for this parser (this is the inner parser).

        # Temporarily change new lexer's token table.
        lexer_to_use_usual_table = lexer_to_use.token_table
        lexer_to_use.set_token_table(self.token_table)

        # Swap the lexer in.
        usual_lexer = self.lex
        self.lex = lexer_to_use # Swap the lexer.

        try:
            parsed_subexpression = self.parse("IGNORED", pstate=pstate,
                                    partial_expressions=True,
                                    skip_lex_setup=True)
        except ParserException:
            print("Error in `parse_from_lexer` method, in call to `parse` method"
                    " using a different parser's lexer for a subexpression.",
                    file=sys.stderr)
            raise
        finally:
            # Restore the temporary lexer's token table.
            lexer_to_use.set_token_table(lexer_to_use_usual_table)
            self.lex = usual_lexer
        return parsed_subexpression

    def parse(self, program, pstate=None, partial_expressions=None,
                                                      skip_lex_setup=False):
        """The main routine for parsing a full program or expression.  Users of
        the class should call this method to perform the parsing operations
        (after defining a grammar, of course).

        Unless there was a parsing failure or `partial_expressions` is true
        then the lexer is left with the end-token as the current token.

        If the `pstate` variable is set then the value will be pushed as the
        initial state on the production rule stack `pstate_stack`.  The stack
        is then cleared after a successful call.  (Set the parser attribute
        directly for more control.)

        The parser's `partial_expressions` attribute will be used unless it is
        overridden by the parameter `partial_expressions` here.  When it is
        true no check is made for the end-token after `recursive_parse` returns
        a value.    The lexer will be left at the last token consumed, so a
        check for the end-token will tell when all the text was consumed.
        Users are responsible for making sure their grammars are suitable for
        this kind of parsing if the option is set.

        If the `skip_lex_setup` parameter is true then the text `program` is
        ignored and lexer setup is skipped.  This is generally ONLY used when
        multiple parsers are parsing from a common text stream, and `parse` is
        called from the method `parse_from_lexer`."""
        if pstate:
            self.pstate_stack = [pstate] # For parsing production rule grammars.
        if partial_expressions is None:
            partial_expressions = self.partial_expressions

        if not skip_lex_setup:
            self.lex.set_text(program)
        begin_tok = self.lex.token # Get the first token to access recursive_parse.
        parse_tree = begin_tok.recursive_parse(0)

        # Finalize type-checking for root when overloading on return types.
        if self.overload_on_ret_types:
            parse_tree.check_types_in_tree_second_pass(root=True)

        # See if we reached the end of the token stream.
        if not self.lex.peek().is_end_token() and not partial_expressions:
            raise IncompleteParseException("Parsing never reached the end of"
                " the text.  Parsing stopped with tokens still in the lexer."
                "  No syntax element was recognized. The last-parsed token had"
                " value '{0}' and label '{1}'.  Parsing stopped before a token"
                " in the lexer with value '{2}' and label '{3}'.  The partial"
                " result returned is:\n{4}"
                .format(self.lex.token.value, self.lex.token.token_label,
                        self.lex.peek().value, self.lex.peek().token_label,
                        parse_tree.tree_repr()))

        if pstate:
            self.pstate_stack = []
        return parse_tree

#
# Copy the convenience functions from builtin_parse_methods to the PrattParser class.
#

for method in builtin_parse_methods.parse_methods:
    setattr(PrattParser, method.__name__, method)

for method in predefined_token_sets.token_defining_methods:
    setattr(PrattParser, method.__name__, method)

#
# Exceptions
#

class IncompleteParseException(ParserException):
    """Only raised at the end of the `PrattParser` function `parse` if tokens
    remain in the lexer after the parser finishes its parsing."""
    pass

class TokenSubclassMeta(type):
    """A trivial metaclass that will actually create the `TokenSubclass`
    objects.  Since tokens are represented by classes, rather than instances,
    this is necessary in order to change their `__repr__` (the defalt one is
    ugly for tokens) and to overload operators to work for token operands
    in the EBNF-like grammar."""
    def __new__(mcs, name, bases, dct):
        new_class = super(TokenSubclassMeta, mcs).__new__(mcs, name, bases, dct)

        # Below is ugly, but avoids mutual import problems.  Used as an easy
        # way to define token addition so that it works in the grammars defined
        # by the ebnf_classes_and_operators module.
        from .ebnf_classes_and_operators import (
                                     Tok, Not, Prec, nExactly, nOrMore, Repeat)
        # These are saved in a dict below because if they are made attributes
        # then Python 2 complains about "TypeError: unbound method Tok() must
        # be called with TokenClass_k_lpar instance as first argument (got
        # TokenSubclassMeta instance instead)".
        new_class.prod_rule_funs = {
                "Tok": Tok,
                "Not": Not,
                "Prec": Prec,
                "nExactly": nExactly,
                "nOrMore": nOrMore,
                "Repeat": Repeat,
                }
        return new_class

    #
    # Define a nicer-looking __repr__, since the classes represent tokens.
    #

    def __repr__(cls):
        """The representation for tokens.  Tokens are commonly used in the
        code but, being classes, have an ugly default `__repr__` when printed out.
        In this metaclass we can define a better `__repr__` for tokens."""
        string = "TokenClass_{0}".format(cls.token_label)
        return string

    #
    # These overloads work with the ebnf_classes_and_operators module.
    #

    # TODO: Could have a flag to turn overloads on and off, maybe.
    # Might want to turn off when not processing a grammar expression
    # using the tokens, but it really shouldn't matter much.
    def __add__(cls, other):
        """Addition of two tokens is defined to simply return a tuple of
        both tokens.  This is so raw tokens can be used in the operator
        overloaded form of defining production rules for a grammar."""
        return cls.prod_rule_funs["Tok"](cls) + other

    def __radd__(cls, left_other):
        """The right version of `__add__` above."""
        return left_other + cls.prod_rule_funs["Tok"](cls)

    def __or__(cls, other):
        """The `|` symbol simply converts this object into an `ItemList`
        and then calls `__or__` for those objects."""
        return cls.prod_rule_funs["Tok"](cls) | other

    def __ror__(cls, left_other):
        """The right version of `__or__` above."""
        return left_other | cls.prod_rule_funs["Tok"](cls)

    def __rmul__(cls, left_other):
        """The expression `n*token` for an int `n` is "n occurrences of"
        `token`."""
        return cls.prod_rule_funs["Repeat"](left_other, cls)

    def __rpow__(cls, left_other):
        """The expression `n**token` for an int `n` is "n or more occurrences of"
        `token`."""
        return cls.prod_rule_funs["nOrMore"](left_other, cls)

    def __invert__(cls):
        """Define the `~` operator for production rule grammars."""
        return cls.prod_rule_funs["Not"](cls)

    def __getitem__(cls, arg):
        """Define the bracket indexing operator for production rule grammars
        to set the precedence."""
        return cls.prod_rule_funs["Prec"](cls, arg)

def token_subclass_factory():
    """This function is called from the `create_token_subclass` method of
    `TokenTable` when it needs to create a new subclass to begin
    with.  It should not be called directly.

    Create and return a new token subclass which will be modified and used
    to represent a particular kind of token.  Specifically, each scanned token
    matching the regex defined for tokens with a given token label is
    represented as an instance of the subclass created by calling this function
    (with further attributes, such as the token label, added to it).

    Using a separate subclass for each token label allows for attributes
    specific to a kind of token (including head and tail handler methods) to
    later be added to the class itself without conflicts.  This function
    returns a bare-bones subclass without any head or tail functions, etc."""

    class TokenSubclass(TokenSubclassMeta("TokenSubclass", (object,), {}), TokenNode):
    #class TokenSubclass(TokenNode, metaclass=TokenSubclassMeta):  # Python 3
    #class TokenSubclass(TokenNode):                               # No metaclass.
        """The factory function returns this class to represent tokens.  It is a
        subclass of the `TokenNode` class, defined in the lexer module."""
        static_prec = 0 # The prec value for this kind of token, with default zero.
        token_label = None # Set to the actual value later, by create_token_subclass.
        #parser_instance = None # Set by recursive_parse. AVOID if not needed.

        def __init__(self, value):
            """Initialize an instance of the subclass for a token of the kind
            labeled with `token_label`.  The `value` is the actual parsed
            string from the text.  This instance represents the token."""
            super(TokenSubclass, self).__init__() # Call base class __init__.
            self.value = value # Set from lex.token_generator; static value=None.

            # The `expanded_formal_sig` attr is set upon parsing.  It is the
            # expanded form of one of the formal sigs which were registered
            # with the token (the expansion handles wildcards, repeat options,
            # etc.)  It is the signature which matched the actual args.  The
            # `self.expanded_formal_sig` has an attribute `original_formal_sig`
            # which is the original, unexpanded formal signature that matched
            # (after expansion) the actual arguments.  After parsing it is set
            # as the token attribute `original_formal_sig`.  This is important
            # because the `eval_fun` and `ast_data` for tokens are saved in
            # dicts keyed by the original signature at the time when they are
            # defined (via `modify_token`).  So we need the resolved original
            # signature to look up the value.  (Note that if overloading on
            # return types is turned off then these dicts are keyed only on the
            # argument portion of the original typesig.)
            self.original_formal_sig = "Unresolved" # The matching orig sig.
            self.expanded_formal_sig = "Unresolved" # Expanded version of above.
            self.actual_sig = "Unresolved" # The actual signature.

        @classmethod
        def prec(cls):
            """Return the precedence for the token.  This is currently a static
            value for each type of token.  Later it may be dynamic value
            associated with the particular tail function which is selected in a
            given context. Update: may become an attribute of a construct and
            no longer of a token."""
            return cls.static_prec

        def process_not_in_tree(self):
            """Removes any immediate children which have `not_in_tree` set."""
            modified_children = []
            for child in self.children:
                if not hasattr(child, "not_in_tree"):
                    modified_children.append(child)
                else:
                    modified_children += child.children
            self.children = modified_children

        def process_and_check_node(self, construct,
                                   val_type_override=None, all_vals_override=None,
                                   typesig_override=None):
            """This routine is automatically called just after a handler
            function returns a subtree.  It is called for the root of the
            returned subtree.  It sets some attributes and checks that the
            actual types match some defined type signature for the function.

            If `val_type_override` is set to a `TypeObject` instance then the
            return type of both the `expanded_formal_sig` and the `actual_sig`
            for the node is set to that type *after* the first pass of
            processing and type-checking for the subtree is finished.  (This
            option does not currently work for two-pass checking when
            overloading on return types is used.)  This option is useful for
            handling things like parentheses and brackets which inherit the
            type of their child (assuming the parens and brackets are kept as
            nodes in the parse tree and not eliminated).  The override value is
            used for type-checking farther up the expression tree.

            If `all_vals_override` is set to a `TypeObject` instance then all
            the possible signatures have their `val_type` changed to that type
            *before* any checking is done.  This should work for both one and
            two-pass checking, but no check is made for producing duplicate
            types due to the `val_type` changes.

            The `typesig_override` argument must be a `TypeSig` instance.  If
            set it will be *assigned* to the node as its only possible
            `expanded_formal_sig` before type checking (instead of looking up
            the registered ones).  Type checking then proceeds as usual."""

            # Get all the sigs registered for the node's construct.
            if typesig_override is not None:
                all_possible_sigs = [typesig_override]
            else:
                all_possible_sigs = construct.original_sigs
            if all_vals_override:
                all_possible_sigs = [TypeSig(all_vals_override, s.arg_types)
                                                      for s in all_possible_sigs]
            self.all_possible_sigs = all_possible_sigs # Temporary attribute.

            # Do the actual checking.
            if not self.parser_instance.overload_on_ret_types: # One-pass.
                self._check_types_one_pass()
            else: # Two-pass.
                self._check_types_first_of_two_passes()
                # If we have a *unique* matching sig, run pass two on the
                # subtree.  In this case, since the signature is fixed by
                # argument types (regardless of where the top-down pass
                # starts from) we can in this case resolve the types in the
                # subtree early.  Note `check_types_in_tree_second_pass` is
                # also called on the root node from the `parse` method.
                if len(self.matching_sigs) == 1: # matching_sigs set by _check_types
                    self.check_types_in_tree_second_pass()

            # Implement val_type override if set.
            if val_type_override:
                # Note that the original_formal_sig attribute was already set.
                # The ast_data and eval_fun are keyed on that.
                self.expanded_formal_sig = TypeSig(val_type_override,
                                                   self.expanded_formal_sig.arg_types)
                self.actual_sig = TypeSig(val_type_override, self.actual_sig.arg_types)

        def _check_types_one_pass(self):
            """Utility function called from `process_and_check_node` to check
            the actual types against their signatures when overloading is only on
            argument types."""
            all_possible_sigs = self.all_possible_sigs

            # One-pass, each child c has a unique c.expanded_formal_sig already set.
            list_of_child_sig_lists = [[c.expanded_formal_sig] for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)
            # Below all_possible_sigs is saved ONLY for printing error messages.
            self.all_possible_sigs = all_possible_sigs

            # No overloading on return types so we can finalize the actual types.
            if len(self.matching_sigs) != 1:
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution: The actual argument types match"
                        " multiple signatures.")

            # Found a unique signature; set the node's expanded_formal_sig attribute.
            # Saved sig used for eval_fun resolution, ast_data, semantic action, etc.
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type,
                                      [c.actual_sig.val_type for c in self.children])

            # Delete some temporary attributes no longer needed.
            delattr(self, "matching_sigs")
            delattr(self, "all_possible_sigs")

        def _check_types_first_of_two_passes(self):
            """Utility function called from `process_and_check_node` to do the
            first pass in checking the actual types against their signatures.
            Two-pass checking is needed for overloading on return types.  First
            pass goes up the tree, second pass goes back down."""
            all_possible_sigs = self.all_possible_sigs

            # First pass case, multiple sigs in child's self.matching_sigs list.
            list_of_child_sig_lists = [c.matching_sigs for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)

        def check_types_in_tree_second_pass(self, root=False):
            """Recursively run the second pass on the token subtree with the
            `self` node as the root.

            This method currently still needs to be explicitly called for the
            root of the final parse tree, from the `PrattParser` method
            `parse`, as well as from the checking routines here to do partial
            checks on subtrees which are already resolvable."""
            unresolved_children = [
                    c for c in self.children if hasattr(c, "matching_sigs")]
            self._check_types_pass_two() # Call first on self to do top-down.
            for child in unresolved_children: # Recurse on unprocessed children.
                child.check_types_in_tree_second_pass()
            # Delete childrens' matching_sigs lists after they are no longer needed.
            # This also acts as an indicator that the node has been resolved.
            for child in unresolved_children:
                delattr(child, "matching_sigs")
            if root:
                # The final pass in _check_types that deletes these attrs doesn't get
                # run on root, so it is explicitly done here when `root` flag is true.
                delattr(self, "matching_sigs")
                delattr(self, "all_possible_sigs")

        def _check_types_pass_two(self):
            """A second pass is only used when overloading on return types is
            allowed.  It is a top-down pass where each node chooses a unique
            final signature for each of its children.  It depends on the
            node attribute `self.matching_sigs` having been set in the first
            pass."""
            # On FIRST pass: on the way *up* the tree (after getting the
            # literal tokens, the leaves of the tree) get all the signature
            # types for a node which match in arguments for *some* possible
            # return-type choice of the children.  Same as the one-pass
            # version, but now sets of possibilities are allowed and state is
            # saved for the second pass to use: the list of matching sigs is
            # temporarily saved with the node in the self.matched_sigs
            # attribute.
            #
            # Summary: first pass, bottom-up, find all sigs that match possible
            # val_types of the node's children, across all arguments.
            #
            # After the first pass the root should have a unique sig; if not
            # there is ambiguity.  (Each node saved a set of sigs that is
            # satisfiable by some realizable choice of child sigs, and parents
            # can force children to assume any of their possible types).
            #
            # On SECOND pass: On the way *down* the tree, parents choose one
            # sig as final for each child and set it in that child's node as
            # the new self.matching_sigs.  This should always be a unique sig;
            # otherwise there is ambibuity.  Recursively called on children.
            #
            # Summary: second pass, top-down, root is unique and parents assign
            # and set the (unique) signature for each of their children.
            #
            # Note that this algorithm works just as well if the second pass is
            # run on each subtree as soon as the subtree root has a unique
            # signature, and the recursion only goes down to subtrees with
            # roots having a unique signature.  This yields partial results and
            # some error conditions sooner, and is what is implemented here.

            if len(self.matching_sigs) != 1: # The root case needs this.
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution (second pass).  Possible type "
                        "assignments for the children/arguments of the token node match"
                        " {0} possible node signatures: {1}.  Uniqueness is required."
                        .format(len(self.matching_sigs), self.matching_sigs))

            # We have a unique signature; set the node's type attributes
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            # Start setting the actual signature; children will fill arg types
            # when resolved.
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type, [])

            # Set the actual_sig arg_type for the parent (appending in sequence with others).
            if self.parent is not None:
                parent_args_so_far = list(self.parent.actual_sig.arg_types)
                parent_args_so_far.append(self.expanded_formal_sig.val_type)
                self.parent.actual_sig = TypeSig(self.parent.actual_sig.val_type,
                                                 parent_args_so_far)

            # Update the matching_sigs attribute for each child (should be singleton).
            for count, child in enumerate(self.children):
                if not hasattr(child, "matching_sigs"):
                    continue # Already resolved.
                matched_sigs = TypeSig.get_child_sigs_matching_return_arg_type(
                                      child, self.expanded_formal_sig.arg_types[count],
                                      child.matching_sigs)
                # From the first pass, we know at least one child sig matches.
                assert len(matched_sigs) != 0 # Debug.
                if len(matched_sigs) > 1:
                    # Recursion could catch this on the next step, but better err msg.
                    child._raise_type_mismatch_error(matched_sigs,
                        "Token node has multiple signatures with return type matching "
                        "type of parent (pass two). Parent expects type '{0}'.  Defined"
                        " signatures are: {1}."
                        .format(self.expanded_formal_sig.val_type, child.matching_sigs))
                child.matching_sigs = matched_sigs
            return

        def _raise_type_mismatch_error(self, matching_sigs, basic_msg):
            """Raise an error, printing a helpful diagnostic message.  Assumes
            that `_check_types` has been called (to set `self.all_possible_sigs`)."""
            # TODO: Will the self.expanded_formal_sig *ever* be resolved when this routine is
            # called?  If not, then it is not very useful and message could be reworded.
            diagnostic = ("  The current token has value '{0}' and label '{1}'.  "
                         " Its expanded formal signature is {2}.  The"
                         " children/arguments have token labels and values of {3} and "
                         "value types {4}.  The list of matching signatures "
                         "is {5}.  The list of possible signatures was {6}"
                         .format(self.value, self.token_label,
                             self.expanded_formal_sig,
                             list(c.summary_repr() for c in self.children),
                             # Note this below can be "Unresolved", better message?
                             list(c.expanded_formal_sig.val_type
                                  if not isinstance(c.expanded_formal_sig, str)
                                  else c.expanded_formal_sig for c in self.children),
                             matching_sigs, self.all_possible_sigs))
            raise TypeErrorInParsedLanguage(basic_msg + diagnostic)

        #
        # Evaluations and semantic actions.
        #

        @property
        def eval_fun(self):
            """Return the evaluation function saved with the winning construct
            dispatched for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_eval_fun(orig_sig, token_value_key=self.value)

        @property
        def ast_data(self):
            """Return the ast data saved with the winning construct dispatched
            for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_ast_data(orig_sig, token_value_key=self.value)

        def eval_subtree(self):
            """Run the saved evaluation function on the token, if one was
            registered with it.  Returns `None` if no evaluation function is found."""
            orig_sig = self.original_formal_sig # Set during parsing.
            eval_fun = self.eval_fun # Property method above.

            # TODO: Consider if returning None is better than raising exception...
            if not eval_fun:
                return None

            # TODO: Consider if special exception should be raised.
            #if not eval_fun:
            #    raise ParserException("An evaluation function is needed for token with "
            #            "value '{0}' and label '{1}' but no defined and matching "
            #            "evaluation function was found in the dict of eval functions.  "
            #            "The resolved original signature is {2} and the resolve expanded"
            #            " signature is {3}.  The resolved construct_label is {4}.  The "
            #            "token's eval_fun_dict is:\n   {5}."
            #            .format(self.value, self.token_label, orig_sig, sig,
            #                    self.construct_label, self.eval_fun_dict))

            return eval_fun(self)

        #
        # The main recursive_parse function.
        #

        def get_jop_token_instance(self, lex, processed_left, extra_data, subexp_prec):
            """Returns an instance of the jop token iff one should be inferred in the
            current context; otherwise returns `None`."""
            # TODO: extra_data arg now holds subexp_prec as field.
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler

            # Not if jop token is undefined for the parser.
            if not parser_instance.jop_token_subclass:
                return None

            # Not if at end of expression.
            if lex.peek().is_end_token():
                return None

            # Not if the ignored token for jop is set but not present.
            if parser_instance.jop_ignored_token_label and (
                          parser_instance.jop_ignored_token_label
                          not in lex.peek().ignored_before_labels()):
                return None

            # Now infer a jop, but only if 1) its prec would satisfy the while loop
            # in `recursive_parse` as an ordinary token, 2) the next token has
            # a head handler defined in the conditions when the jop will need
            # to run its head handler, and 3) the next token similarly has no
            # tail handler in the context.
            if parser_instance.jop_token_subclass.prec() > subexp_prec:
                # Provisionally infer a jop; create a subclass instance for its token.
                #
                # Todo: Maybe for jop and null-string tokens define methods
                # get_jop_token_instance() which gets the token but calls the
                # lexer to dress it up more like a "real" token, with ignored_before
                # and line numbers, etc. (without putting it in the buffer, of course).
                jop_instance = parser_instance.jop_token_subclass(None)
                jop_instance.extra_data = extra_data

                # This is a little inefficient (since it uses a `go_back` call)
                # but we need to be sure that when the tail handler of the jop
                # is called and it reads a token that that token has a head
                # handler defined for it *in that precondition context*.
                # Otherwise, no jop will be inferred.  We also make sure that
                # it has no tail handler in the context, since then it would be
                # a lower-precedence (lower precedence because we broke out of
                # the loop above) infix or postfix operator, and no jop is
                # inferred before another operator).
                curr_token = lex.next()
                try:
                    # Dispatch here WITHOUT CALLING, since calling will consume
                    # another token; also, deeper-level recursions could cause false
                    # results to come up the recursion chain.  We are just testing
                    # what handlers are defined for the token.
                    _peek_head_handler, head_construct = dispatch_handler(
                                                   HEAD, curr_token, lex, extra_data)
                    try: # Found head handler, now make sure it has no tail handler.
                        _peek_tail_handler, tail_construct = dispatch_handler(
                                   TAIL, curr_token, lex, extra_data, processed_left)
                    except NoHandlerFunctionDefined:
                        # This is the only case where an actual token is returned.
                        return jop_instance
                    else:
                        return None
                except NoHandlerFunctionDefined:
                    return None # No precondition matches, assume no jop.
                finally:
                    #delattr(curr_token, "extra_data") # Only needed if pushback below, not go_back.
                    lex.go_back(1)
            else:
                return None

        def dispatch_null_string_handler(self, head_or_tail, lex, subexp_prec,
                                         extra_data, processed_left=None):
            """Check for any possible matching null-string token handlers;
            return the token and the matching handler if one is found.

            Note that the precedence for a null-string token is set to
            `subexpr_prec`, so it would always have activated the while loop if
            it were a real token."""
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            # See if a null-string token is set and a handler matches preconds.
            if not parser_instance.null_string_token_label:
                return None, None, None
            else:
                # TODO: Later don't re-create each time, save one.
                null_string_token = parser_instance.null_string_token_subclass(None)
            null_string_token.extra_data = extra_data

            curr_token = None
            handler_fun = None
            construct = None
            try:
                handler_fun, construct = dispatch_handler(head_or_tail,
                                                          null_string_token,
                                                          lex, extra_data, processed_left)
                curr_token = null_string_token
            except NoHandlerFunctionDefined:
                pass
            return curr_token, handler_fun, construct

        def recursive_parse(self, subexp_prec, only_head=False):
            """Parse a subexpression as defined by token precedences. Return
            the result of the evaluation.  Recursively builds up the final
            result in `processed_left`, which is the tree for the part of the
            full expression to the left of the current token.

            The list `lookbehind` saves all the previously evaluated
            subexpressions at this level of recursion (i.e., at the top level
            in the same subexpression) and passes it to the dispatched tail
            handlers, in case that routine wants to make use of it.  For
            example, the ordinal position of the token in the top level of the
            subexpression can be calculated from the length of `lookbehind`.

            This function is made a method of `TokenSubclass` so that handler
            functions can easily call it by using `tok.recursive_parse`, and
            also so that it can access the lexer without it needing to be
            passed as an argument.  It is basically a static function,
            though.

            The `extra_data` attribute is set for all triggering tokens, and is
            guaranteed to be available for precondition functions and for
            handler functions.  It is set before any dispatches or recursive calls,
            and is deleted from the token after the recursive call.  It is an
            advanced feature which most users will not need."""
            # Note that all the dispatching functions set the `extra_data`
            # attribute of their token before the dispatching is done, but they
            # do not update `extra_data` itself in any way.

            # Note on below code: It is tempting for efficiency to define a jop
            # and null-string token instance, save it, and only use it when
            # necessary (replacing it only when used).  But some things need to
            # be considered.
            #
            # Now that handlers are not with tokens, that is no longer a
            # concern... TODO go ahead and do this.
            #
            # Is there any special attribute or other thing that is assigned on
            # creation which might change?  Either way, you should probably add
            # extra things like line numbers to mimic ordinary tokens. Note
            # that currently you only really pay the creation cost if you
            # actually use the jop or null-string feature, but a lot of dummy
            # instances are created if you do.

            # This err check catches some cases of tokens defined via Lexer, not all.
            if not hasattr(self, "token_kind"):
                raise ParserException("All tokens used in the parser must be"
                        " defined in via parser's methods, not the lexer's.")

            #
            # Initialize, and set some shorter aliases.
            #

            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            lex = self.token_table.lex
            extra_data = ExtraDataTuple(lookbehind=[], constructs=[],
                                        subexp_prec=subexp_prec)

            #
            # Start the actual Pratt parsing recursion.
            #

            curr_token, head_handler, construct = self.dispatch_null_string_handler(
                                                     HEAD, lex, subexp_prec, extra_data)
            if not curr_token: # No null-string token fired, so use normal next() call.
                curr_token = lex.next()
                head_handler, construct = dispatch_handler(
                                                     HEAD, curr_token, lex, extra_data)

            extra_data.constructs.append(construct)

            # TODO: Should the root of processed_left be set for is_head instead, for
            # general case?  Or set "head_trigger_token" to label instead of None?
            # Consider how lookup will work in usual and general cases of arbitrary
            # token as subtree root.
            curr_token.is_head = True # Used to look up eval_fun and ast_data later.

            processed_left = head_handler()

            delattr(curr_token, "extra_data") # Delete after recurse, allow mem cleanup.
            extra_data.lookbehind.append(processed_left)
            extra_data.constructs.append(construct)

            if only_head:
                return processed_left

            while True:

                #
                # The loop below is the main loop in ordinary Pratt parsing.  The
                # Outer loop is ONLY for the special case when a jop is defined.
                #

                # TODO: Consider modification like code below to allow
                # precedences per constuct, which also makes "prec - 1" no
                # longer necessary for right assoc when property is set for the
                # construct itself.  See what performance hit it has, one
                # go_back per subexpression.  Note that jops use a single
                # go_back already when they are defined...
                #
                # The ugly comment-string code below works.  It just pulls the
                # token-dispatching out to before the precedence test.
                # Obviously could then use some cleanup and refactoring, too.
                # Consider possible interactions with jop and null-string
                # tokens, but they don't do a `next` call anyway.  (Is it
                # better to pull out the ns_token dispatch, at least?  In
                # regular code, how to get null-string to appear at end of a
                # subexpression?)
                #
                # Argument it works: This code is doing exactly the same
                # dispatching as it would inside the loop test, but it is doing
                # it before the loop test.  The loop test never modifies
                # anything.  If the test fails the effects of the dispatches
                # are undone.
                """
                while True:
                    #err = None
                    ns_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if ns_token:
                        curr_token = ns_token
                        peek_prec = lex.token.prec()
                        #peek_prec = construct.prec() # Switch to this...
                    else:
                        curr_token = lex.next()
                        try:
                            tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                            lex, extra_data, processed_left)
                            peek_prec = lex.token.prec()
                            #peek_prec = construct.prec() # Switch to this...
                        except NoHandlerFunctionDefined as e:
                            # If no construct at all then can't have tail handler so
                            # prec should be 0.  But if it fails due to a precond,
                            # token itself could still have a prec > 0.  In that case
                            # it will get inside the loop and fail, but it really
                            # shouldn't have gotten inside.
                            #
                            # Only one test changes, and new one is commented out in
                            # the test file under the old one.
                            #err = e
                            peek_prec = -1 # Always fail test and break.
                            #peek_prec = lex.token.prec()

                    #test_assoc = False if err else (peek_prec == subexp_prec and
                    #                                construct.assoc == "right")
                    test_assoc = peek_prec == subexp_prec and construct.assoc == "right"
                    if peek_prec > subexp_prec or test_assoc:
                        #if err: # Error would have been found inside loop, now above.
                        #    raise err # Avoid error msg changing (makes test fail).
                        processed_left = tail_handler()
                        delattr(curr_token, "extra_data")
                        extra_data.lookbehind.append(processed_left)
                        extra_data.constructs.append(construct)
                    else:
                        if not ns_token:
                            lex.go_back(1)
                        break
                """

                while lex.peek().prec() > subexp_prec:

                    curr_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if not curr_token: # No null handler fired off, get regular way.
                        curr_token = lex.next()
                        tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                        lex, extra_data, processed_left)

                    processed_left = tail_handler()
                    delattr(curr_token, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)

                #
                # Broke out of main loop, determine whether or not to infer a jop.
                #

                jop_instance = self.get_jop_token_instance(
                                         lex, processed_left, extra_data, subexp_prec)
                if jop_instance:
                    jop_tail_handler, construct = dispatch_handler(TAIL, jop_instance,
                                                        lex, extra_data, processed_left)
                    processed_left = jop_tail_handler()
                    delattr(jop_instance, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)
                else:
                    break

            return processed_left

        #
        # Copying instances of tokens.
        #

        def __copy__(self):
            """Return a shallow copy of the token."""
            return copy.copy(self)

        #
        # Some representations that apply to the subclasses.
        #

        def summary_repr_with_types(self):
            """A short summary repr of the node, without its children."""
            return ("<" + str(self.token_label) +
                    ",'" + str(self.value) +
                    "'," + str(self.expanded_formal_sig.val_type) + ">")

        def tree_repr_with_types(self, indent=""):
            """Token representation as the root of a parse subtree, with formatting.
            The optional `indent` parameter can be either an indent string or else
            an integer for the number of spaces to indent.  Note that the ordinary
            `tree_repr` method without types is also available, inherited from
            the base node object."""
            try:
                num_indent = int(indent)
            except ValueError:
                pass
            else:
                indent = " " * num_indent
            string = indent + self.summary_repr_with_types() + "\n"
            for c in self.children:
                string += c.tree_repr_with_types(indent=indent+" "*4)
            return string

        def string_repr_with_types(self):
            """A string repr for the tree that includes type information."""
            string = self.summary_repr_with_types()
            if self.children:
                string += "("
                string += ",".join(c.string_repr_with_types() for c in self.children)
                string += ")"
            return string

        @classmethod
        def class_repr(cls):
            """Print out the `TokenSubclass` classes (representing tokens) in a
            nice way.  The default is hard to read."""
            string = "Token({0})".format(cls.token_label)
            return string

    return TokenSubclass # Return from token_subclass_factory function.

#
# Parser
#

def lexer_add_parser_instance_attribute(lexer, token):
    """Passed to lexer to add a `parser_instance` attribute to each token it
    returns.  This attribute is added to instances at the lexer, from its
    current token table, because of the case where parsers call other parsers.
    (It is not added to general token subclasses in `def_token_master` because
    parsers could potentially share token subclasses.)"""
    token.parser_instance = lexer.token_table.parser_instance # From token table.
    return token

# Could also add parser_instance and construct as fields of the extra data tuple.
# Could extra_data also be passed to handler functions?  Nice to have construct
# instance available there, perhaps.  TODO: Consider.
ExtraDataTuple = namedtuple("ExtraHandlerData", ["lookbehind",
                                                 "constructs",
                                                 "subexp_prec"])

class PrattParser(object):
    """A parser object.  Each parser object contains a table of defined tokens,
    a lexer, a table of constructs, and a table of defined types."""
    def __init__(self, max_peek_tokens=None,
                       max_deque_size=None,
                       lexer = None,
                       default_begin_end_tokens=True,
                       type_table = None,
                       skip_type_checking=False,
                       overload_on_arg_types=True,
                       overload_on_ret_types=False,
                       partial_expressions=False,
                       parser_label=None,
                       raise_on_equal_priority_preconds=False):
        """Initialize the parser.

        The `max_peek_tokens` parameter is an optional arbitrary limit on the
        level of peeks allowed in the lexer.  Setting to 1 limits it to a
        single token lookahead.  The default setting `None` gives
        peek-on-demand as far ahead as requested.

        The `max_deque_size` parameter is an optional limit on the size of the
        deque that the lexer keeps for previous tokens, the current token, and
        requested peek tokens.  The default is for it to grow arbitrarily
        (though it is reset on each parse).  Needs to be large enough for the
        max level of peeks required plus the max `go_back` level required.

        If a `Lexer` instance is passed in the parser will use that lexer and
        its token table, otherwise a new lexer is created.  The any other lexer
        options are ignored.

        No default begin and end functions will be set if a lexer is passed in,
        regardless of the value of `default_begin_end_tokens`.  Otherwise,
        default begin and end tokens will be defined unless
        `default_begin_end_tokens` is set false (note that creating them by
        default is the opposite of the default behavior for the lower-level
        Lexer class).

        Setting `skip_type_checking=True` is slightly faster since typing is
        not being used at all.  Note that overloading depends on type-checking
        to resolve the actual types, so this flag implies that the overload
        flags are all false.  The default is false.  It should be possible to
        define types, use them during testing, and then turn checking off ---
        provided overloading is not used to get different evaluation functions
        or AST data elements for different overloads.

        The `overload_on_arg_types` flag specifies whether or not to overload
        on argument types.  The default is true.  Cannot be changed after
        initialization.

        Setting `overload_on_ret_types` also overloads on argument types.  It
        requires an extra walk of the token tree, and implies overloading on
        argument types.  The default is false.  Cannot be changed after
        initialization.

        If `partial_expressions` is set true then no check will be made in the
        `parse` method to see if the parsing consumed up to the end-token in
        the lexer.  Multiple expression text can be parsed by repeatedly
        calling `parse` when this option is true and checking whether the
        lexer's current token is the end-token.

        The `parser_label` is an optional descriptive string for a parser.
        These can be useful in debugging when they appear in error messages,
        especially when working with multiple parser instances.

        If `raise_on_equal_priority_preconds` is true then an exception will be
        raised if two precondition functions are registered with the same
        trigger token in the same head or tail position which have the same
        precondition priority.  The default is false, and the first-defined
        matching precondition function of the same priority will win any
        competition when several are true.  This option can be used to ensure
        at language define-time that there is no definition-order dependence in
        dispatching.  If two such preconditions functions are mutually
        exclusive there is no problem with them having the same priority, but
        this condition cannot be checked by a program.  A small difference can
        be added."""

        if parser_label:
            self.parser_label = parser_label # Set first, for error messages.
        else:
            self.parser_label = None

        ## Type-checking options below; these cannot be changed after initialization.
        if overload_on_ret_types:
            overload_on_arg_types = True # Overload on ret implies overload on args.
        self.skip_type_checking = skip_type_checking # Skip all type checks, faster.
        if not skip_type_checking:
            self.overload_on_arg_types = overload_on_arg_types
            self.overload_on_ret_types = overload_on_ret_types
        else: # Overloading requires type checking.
            self.overload_on_arg_types = False
            self.overload_on_ret_types = False

        # If exceptions are not raised on ties then with non-mutually-exclusive
        # precond functions the first-set one will have precedence when they
        # are both true.  Need to define this before registering any handlers (
        # which is done below in `def_begin_end_tokens`).
        self.raise_on_equal_priority_preconds = raise_on_equal_priority_preconds
        #self.raise_on_equal_priority_preconds = True # DEBUG

        self.construct_table = ConstructTable(parser_instance=self) # Dict of constructs.
        self.default_construct_label_number = 0 # For unique precondition labels.

        if lexer: # Lexer passed in.
            self.lex = lexer
            self.token_table = lexer.token_table
        else: # No Lexer passed in.
            self.token_table = TokenTable(
                                token_subclass_factory_fun=token_subclass_factory)
            self.lex = Lexer(self.token_table,
                             max_peek_tokens=max_peek_tokens,
                             max_deque_size=max_deque_size,
                             default_begin_end_tokens=False)
            # Set the begin and end tokens unless the user specified not to.
            if default_begin_end_tokens:
                self.def_begin_end_tokens() # Use function's defaults.
        self.lex.default_helper_exception = ParserException # Default for match_next, etc.
        # Add mod function to lexer here, works even if they passed in a lexer.
        self.lex.final_mod_function = lexer_add_parser_instance_attribute

        self.token_table.parser_instance = self # Give token table ref to parser.

        if type_table:
            self.type_table = type_table
        else:
            self.type_table = TypeTable(self)

        self.num_lookahead_tokens = max_peek_tokens
        self.jop_token_label = None # Label of the jop token, if any.
        self.jop_token_subclass = None # The actual jop token, if defined.
        self.null_string_token_label = None # Label of the null-string token, if any.
        self.null_string_token_subclass = None # The actual null-string token, if any.

        self.partial_expressions = partial_expressions # Whether to parse multiple expressions.

        self.pstate_stack = [] # Stack of production rules used in grammar parsing.
        self.top_level_production = False # If true, require grammar parses to consume to end.
        self.disable_pstate_processing = False # Set to temporarily disable grammar parsing.

    #
    # Methods defining tokens.
    #

    def def_token_master(self, token_label, regex_string=None, on_ties=0, ignore=False,
                         token_kind="regular", ignored_token_label=None,
                         matcher_options=None):
        """The master method for defining tokens; all the convenience methods
        actually call it.  Allows for factoring out some common code and
        keeping the attributes of all the different kinds of tokens up-to-date.
        This routine calls the underlying lexer's `def_token` to get tokens and
        then adds extra attributes needed by the `PrattParser` class.

        The `token_kind` argument must be one of the following strings:
        `"regular"`, `"ignored"`, `"begin"`, `"end"`, `"jop"`, or
        `"null-string"`.  The `ignored_token_label` is used only when defining
        a jop.

        Tokens can be shared between parsers if all their properties are the
        same.  Note that for now this includes the precedence value for any
        tail handlers (since that is made a token attribute).  Null-string and
        jop tokens are the exception, but they are special in that they are
        never returned by the lexer, only by a particular parser."""
        token_table = self.token_table

        if token_kind == "regular":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=ignore, matcher_options=matcher_options)

        elif token_kind == "ignored":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=True, matcher_options=matcher_options)

        elif token_kind == "begin":
            tok = token_table.def_begin_token(token_label)
            self.begin_token_label = token_label
            # Define dummy handlers for the begin-token, just to catch errors.
            def begin_head(self, lex):
                """Dummy head handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called head-handler for begin token.")
            def begin_tail(self, lex, left):
                """Dummy tail-handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called tail-handler for begin token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, begin_head, token_label)
            self.def_construct(TAIL, begin_tail, token_label, dummy_handler=True)
            self.begin_token_subclass = tok

        elif token_kind == "end":
            tok = token_table.def_end_token(token_label)
            self.end_token_label = token_label
            # Define dummy handlers for the end-token, just to catch errors.
            def end_head(self, lex):
                """Dummy head handler for end-tokens."""
                raise CalledEndTokenHandler("Called head-handler for end token.")
            def end_tail(self, lex, left):
                """Dummy tail-handler for end-tokens."""
                raise CalledEndTokenHandler("Called tail-handler for end token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, end_head, token_label)
            self.def_construct(TAIL, end_tail, token_label, dummy_handler=True)
            self.end_token_subclass = tok

        elif token_kind == "jop":
            if self.jop_token_subclass:
                raise ParserException("A jop token is already defined.  It must be "
                                      "undefined before defining a new one.")
            self.jop_token_label = token_label
            self.jop_ignored_token_label = ignored_token_label
            tok = token_table.def_token(token_label, None)
            self.jop_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        elif token_kind == "null-string":
            if self.null_string_token_subclass:
                raise ParserException("A null-string token is already defined.  It"
                         " must be undefined before defining an new one.")
            self.null_string_token_label = token_label
            tok = token_table.def_token(token_label, None)
            self.null_string_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        else:
            raise ParserException("Bad call to def_token_master, with unrecognized"
                    ' string "{0}" for the keyword argument token_kind.'
                    .format(token_kind))

        tok.token_kind = token_kind
        tok.is_head = False # Set true in recursive_parse if instance parses as a head.
        return tok

    def def_token(self, token_label, regex_string, on_ties=0, ignore=False,
                  matcher_options=None):
        """Define a token.  Use this instead of the Lexer `def_token` method,
        since it adds extra attributes to the tokens."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore,
                              token_kind="regular", matcher_options=matcher_options)

    def def_ignored_token(self, token_label, regex_string, on_ties=0,
                          matcher_options=None):
        """A convenience function to define a token with `ignored=True`."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore=True,
                              token_kind="ignored", matcher_options=matcher_options)

    def def_begin_end_tokens(self, begin_token_label="k_begin",
                                   end_token_label="k_end"):
        """Calls the `Lexer` method to define begin- and end-tokens.  The
        subclasses are then given initial head and tail functions for use in
        the Pratt parser.  To use the `PrattParser` this method must be called,
        not the method of `Lexer` with the same name (since it also creates
        head and tail handler functions that raise exceptions for better error
        messages).  The default is to call this method automatically on
        initialization, with the default token labels for the begin and end
        tokens.  If the flag `default_begin_end_tokens` is set false on
        `PrattParser` initalization then the user must call this function
        (setting whatever token labels are desired).  Returns a tuple
        containing the new begin and end `TokenNode` subclasses."""
        begin_tok = self.def_token_master(begin_token_label, token_kind="begin")
        end_tok = self.def_token_master(end_token_label, token_kind="end")
        return begin_tok, end_tok

    def def_jop_token(self, jop_token_label, ignored_token_label):
        """Define a token for the juxtaposition operator.  This token has no
        regex pattern.  An instance is inserted in `recursive_parse` when it is
        inferred to be present.  This method must be explicitly called before a
        juxtaposition operator can be used (i.e., before `def_jop`).  The
        parameter `jop_token_label` is the label for the newly-created token
        representing the juxtaposition operator.  The `ignored_token_label`
        parameter is the label of an ignored token which must be present for a
        jop to be inferred.  Some already-defined token is required; usually it
        will be a token for spaces and tabs.  If set to `None` then no ignored
        space at all is required (i.e., the operands can be right next to each
        other)."""
        return self.def_token_master(jop_token_label,
                                     ignored_token_label=ignored_token_label,
                                     token_kind="jop")

    def def_null_string_token(self, null_string_token_label="k_null-string"):
        """Define the null-string token.  This token has no regex pattern.  An
        instance is inserted in `recursive_parse` when it is inferred to be
        present based.  This method must be called before a
        null-string can be used.  The parameter `null_string_token_label` is
        the label for the newly-created tok representing it."""
        return self.def_token_master(null_string_token_label,
                                     token_kind="null-string")

    def get_token(self, token_label):
        """Return the token with the label `token_label`.  The reverse
        operation, getting a label from a token instance, can be done by
        looking at the `token_label` attribute of the token."""
        return self.token_table[token_label]

    #
    # Undefine tokens.
    #

    def undef_token(self, token_label):
        """A method for undefining any token defined by the `PrattParser` methods.
        Since the `token_kind` was set for all tokens when they were defined
        it knows how to undelete any kind of token."""
        # TODO: Make sure this is up-to-date with the what the token_master class does.
        token_table = self.token_table
        tok = token_table[token_label]
        kind = tok.token_kind
        if kind == "jop":
            token_table.undef_token(self.jop_token_label)
            self.jop_token_subclass = None
            self.jop_token_label = None
            self.jop_ignored_token_label = None
        elif kind == "null-string":
            token_table.undef_token(self.null_string_token_label)
            self.null_string_token_subclass = None
            self.null_string_token_label = None
            self.null_string_ignored_token_label = None
        else:
            token_table.undef_token(token_label)

    #
    # Methods to define and undefine constructs.
    #

    def def_construct(self, head_or_tail, handler_fun, trigger_token_label,
                      prec=0, construct_label=None, precond_fun=None,
                      precond_priority=0, val_type=None, arg_types=None,
                      eval_fun=None, ast_data=None, token_value_key=None,
                      dummy_handler=False):
        """Define a construct and register it with the token with label
        `trigger_token_label`.  A token with that label must already be in the
        token table or an exception will be raised.

        Stores the construct instance in the parser's construct table and also
        return the construct instance.

        The `head_or_tail` argument should be set to either `HEAD` or `TAIL`.
        If `head_or_tail==TAIL` then the operator precedence will be set to
        `prec`.  For a head handler the `prec` value is ignored and effectively
        set to zero.  For a tail handler a `prec` value greater than zero is
        required or else an exception will be raised (unless `dummy_handler` is
        set true).  Similarly, an exception is raised for a non-zero `prec`
        value for a head-handler (the default value).

        The `construct_label` is an optional string value which can result in
        better error messages.

        The `eval_fun` and the `ast_data` arguments are saved in dicts
        associated with the type signature.

        If `token_value_key` is set to a string value then that value will be
        part of the key tuple for saving AST data and evaluation functions.
        This can be used, for example, when overloading a generic identifier
        with different evaluation functions for when the identifier value is
        `sin`, `cos`, etc.  In looking up the AST data and evaluation function
        the parsed token's actual string value (from the program text) is used
        as the key.  If any overload of a particular construct provides a
        `token_value_key` string then all the other overloads for that
        construct must also (for the time being, at least)."""
        # Note that the parser_instance attribute of tokens is not necessarily
        # set yet when this method is called.
        if isinstance(arg_types, str):
            raise ParserException("The arg_types argument to token_subclass must"
                    " be None or an iterable returning type labels (e.g., a list"
                    " or tuple).")

        if head_or_tail == TAIL and prec <= 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a tail hander and a precedence of zero or less."
                    .format(trigger_token_label))
        if head_or_tail == HEAD and prec != 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a head hander and a precedence not equal to zero."
                    .format(trigger_token_label))

        if precond_fun is None:
            precond_fun = DEFAULT_ALWAYS_TRUE_PRECOND_FUN

        if trigger_token_label in self.token_table:
            trigger_token_subclass = self.get_token(trigger_token_label)
        else:
            raise ParserException("In call to def_construct: subclass for"
                    " token labeled '{0}' has not been defined.  Maybe try"
                    " calling def_token first.".format(trigger_token_label))
            # Below line formerly just created a subclass, but that can mask errors!
            #TokenSubclass = self.token_table.create_token_subclass(token_label)

        if not hasattr(trigger_token_subclass, "token_kind"):
            raise ParserException("Token with label '{0}'  must be defined by the"
                                  " parser's def_token method, not the lexer's method."
                                  .format(trigger_token_label))

        # TODO: Precedence is currently saved as a token attribute.  Consider
        # saving it in the construct instead.  See main Sphinx docs, unimplemented
        # generalizations.
        if head_or_tail == TAIL:
            if (trigger_token_subclass.static_prec != 0 and
                    prec != trigger_token_subclass.static_prec):
                raise ParserException("Redefining the precedence of the triggering"
                        " token subclass '{0}' to a new value {1} not equal"
                        " to the previous nonzero value of {2}."
                        " The original precedence will never be used.  To actually"
                        " reset the value, set trigger_token_label.static_prec=0"
                        " explicitly before this call to def_construct.  Currently"
                        " all operators with the same triggering token must have"
                        " the same precedence value, regardless of preconditions."
                        .format(trigger_token_label, prec,
                                trigger_token_subclass.static_prec))
            trigger_token_subclass.static_prec = prec # Ignore prec for heads; will stay 0.

        # Create the type sig object.
        if self.skip_type_checking:
            type_sig = None
        else:
            type_sig = TypeSig(val_type, arg_types)

        # Register the handler funs.
        construct = self.construct_table.register_construct(
                                          head_or_tail=head_or_tail,
                                          trigger_token_subclass=trigger_token_subclass,
                                          handler_fun=handler_fun,
                                          precond_fun=precond_fun,
                                          precond_priority=precond_priority,
                                          construct_label=construct_label,
                                          type_sig=type_sig,
                                          eval_fun=eval_fun,
                                          ast_data=ast_data,
                                          token_value_key=token_value_key)
        return construct

    def undef_construct(self, construct, type_sig=None, token_value_key=None):
        """Undefine a construct.  If `type_sig` is passed a `TypeSig` instance then
        only that overload is deleted.  If `token_value_key` is also defined then
        only that token key is unregistered.  Otherwise the full construct is
        removed from the parser's construct table."""
        # Note users themselves could unregister the overloads if they have the
        # construct instance.
        self.construct_table.unregister_construct(construct, type_sig, token_value_key)

    #
    # Methods dealing with types.
    #

    def def_type(self, type_label):
        """Define a type associated with the name `type_label`."""
        return self.type_table.create_typeobject(type_label)

    def undef_type(self, type_label):
        """Undefine the type associated with the name `type_label`."""
        self.type_table.undef_typeobject(type_label)

    #
    # The main parse routines.
    #

    def parse_from_lexer(self, lexer_to_use, pstate=None):
        """The same as the `parse` method, but a lexer_to_use is already assumed to be
        initialized.  This is ONLY used when one parser instance calls another
        parser instance (implicitly, via the handler functions of its tokens).
        The outer parser calls this routine of the inner, subexpression parser.
        Such a call to another parser would look something like::

            alternate_parser.parse_from_lexer(lexer_to_use)

        where `lexer_to_use` is the lexer_to_use of the outer parser.  This routine
        temporarily swaps the token table for the passed-in lexer_to_use to be the
        token table for this parser (remember that this parser is the inner
        parser when this routine is called)."""
        # Note you do not need to set the type_table, since the tokens always
        # have fixed references to their own parser instance.

        # Set up to read from lexer_to_use, after setting its token table to
        # be the token table for this parser (this is the inner parser).

        # Temporarily change new lexer's token table.
        lexer_to_use_usual_table = lexer_to_use.token_table
        lexer_to_use.set_token_table(self.token_table)

        # Swap the lexer in.
        usual_lexer = self.lex
        self.lex = lexer_to_use # Swap the lexer.

        try:
            parsed_subexpression = self.parse("IGNORED", pstate=pstate,
                                    partial_expressions=True,
                                    skip_lex_setup=True)
        except ParserException:
            print("Error in `parse_from_lexer` method, in call to `parse` method"
                    " using a different parser's lexer for a subexpression.",
                    file=sys.stderr)
            raise
        finally:
            # Restore the temporary lexer's token table.
            lexer_to_use.set_token_table(lexer_to_use_usual_table)
            self.lex = usual_lexer
        return parsed_subexpression

    def parse(self, program, pstate=None, partial_expressions=None,
                                                      skip_lex_setup=False):
        """The main routine for parsing a full program or expression.  Users of
        the class should call this method to perform the parsing operations
        (after defining a grammar, of course).

        Unless there was a parsing failure or `partial_expressions` is true
        then the lexer is left with the end-token as the current token.

        If the `pstate` variable is set then the value will be pushed as the
        initial state on the production rule stack `pstate_stack`.  The stack
        is then cleared after a successful call.  (Set the parser attribute
        directly for more control.)

        The parser's `partial_expressions` attribute will be used unless it is
        overridden by the parameter `partial_expressions` here.  When it is
        true no check is made for the end-token after `recursive_parse` returns
        a value.    The lexer will be left at the last token consumed, so a
        check for the end-token will tell when all the text was consumed.
        Users are responsible for making sure their grammars are suitable for
        this kind of parsing if the option is set.

        If the `skip_lex_setup` parameter is true then the text `program` is
        ignored and lexer setup is skipped.  This is generally ONLY used when
        multiple parsers are parsing from a common text stream, and `parse` is
        called from the method `parse_from_lexer`."""
        if pstate:
            self.pstate_stack = [pstate] # For parsing production rule grammars.
        if partial_expressions is None:
            partial_expressions = self.partial_expressions

        if not skip_lex_setup:
            self.lex.set_text(program)
        begin_tok = self.lex.token # Get the first token to access recursive_parse.
        parse_tree = begin_tok.recursive_parse(0)

        # Finalize type-checking for root when overloading on return types.
        if self.overload_on_ret_types:
            parse_tree.check_types_in_tree_second_pass(root=True)

        # See if we reached the end of the token stream.
        if not self.lex.peek().is_end_token() and not partial_expressions:
            raise IncompleteParseException("Parsing never reached the end of"
                " the text.  Parsing stopped with tokens still in the lexer."
                "  No syntax element was recognized. The last-parsed token had"
                " value '{0}' and label '{1}'.  Parsing stopped before a token"
                " in the lexer with value '{2}' and label '{3}'.  The partial"
                " result returned is:\n{4}"
                .format(self.lex.token.value, self.lex.token.token_label,
                        self.lex.peek().value, self.lex.peek().token_label,
                        parse_tree.tree_repr()))

        if pstate:
            self.pstate_stack = []
        return parse_tree

#
# Copy the convenience functions from builtin_parse_methods to the PrattParser class.
#

for method in builtin_parse_methods.parse_methods:
    setattr(PrattParser, method.__name__, method)

for method in predefined_token_sets.token_defining_methods:
    setattr(PrattParser, method.__name__, method)

#
# Exceptions
#

class IncompleteParseException(ParserException):
    """Only raised at the end of the `PrattParser` function `parse` if tokens
    remain in the lexer after the parser finishes its parsing."""
    pass

class TokenSubclassMeta(type):
    """A trivial metaclass that will actually create the `TokenSubclass`
    objects.  Since tokens are represented by classes, rather than instances,
    this is necessary in order to change their `__repr__` (the defalt one is
    ugly for tokens) and to overload operators to work for token operands
    in the EBNF-like grammar."""
    def __new__(mcs, name, bases, dct):
        new_class = super(TokenSubclassMeta, mcs).__new__(mcs, name, bases, dct)

        # Below is ugly, but avoids mutual import problems.  Used as an easy
        # way to define token addition so that it works in the grammars defined
        # by the ebnf_classes_and_operators module.
        from .ebnf_classes_and_operators import (
                                     Tok, Not, Prec, nExactly, nOrMore, Repeat)
        # These are saved in a dict below because if they are made attributes
        # then Python 2 complains about "TypeError: unbound method Tok() must
        # be called with TokenClass_k_lpar instance as first argument (got
        # TokenSubclassMeta instance instead)".
        new_class.prod_rule_funs = {
                "Tok": Tok,
                "Not": Not,
                "Prec": Prec,
                "nExactly": nExactly,
                "nOrMore": nOrMore,
                "Repeat": Repeat,
                }
        return new_class

    #
    # Define a nicer-looking __repr__, since the classes represent tokens.
    #

    def __repr__(cls):
        """The representation for tokens.  Tokens are commonly used in the
        code but, being classes, have an ugly default `__repr__` when printed out.
        In this metaclass we can define a better `__repr__` for tokens."""
        string = "TokenClass_{0}".format(cls.token_label)
        return string

    #
    # These overloads work with the ebnf_classes_and_operators module.
    #

    # TODO: Could have a flag to turn overloads on and off, maybe.
    # Might want to turn off when not processing a grammar expression
    # using the tokens, but it really shouldn't matter much.
    def __add__(cls, other):
        """Addition of two tokens is defined to simply return a tuple of
        both tokens.  This is so raw tokens can be used in the operator
        overloaded form of defining production rules for a grammar."""
        return cls.prod_rule_funs["Tok"](cls) + other

    def __radd__(cls, left_other):
        """The right version of `__add__` above."""
        return left_other + cls.prod_rule_funs["Tok"](cls)

    def __or__(cls, other):
        """The `|` symbol simply converts this object into an `ItemList`
        and then calls `__or__` for those objects."""
        return cls.prod_rule_funs["Tok"](cls) | other

    def __ror__(cls, left_other):
        """The right version of `__or__` above."""
        return left_other | cls.prod_rule_funs["Tok"](cls)

    def __rmul__(cls, left_other):
        """The expression `n*token` for an int `n` is "n occurrences of"
        `token`."""
        return cls.prod_rule_funs["Repeat"](left_other, cls)

    def __rpow__(cls, left_other):
        """The expression `n**token` for an int `n` is "n or more occurrences of"
        `token`."""
        return cls.prod_rule_funs["nOrMore"](left_other, cls)

    def __invert__(cls):
        """Define the `~` operator for production rule grammars."""
        return cls.prod_rule_funs["Not"](cls)

    def __getitem__(cls, arg):
        """Define the bracket indexing operator for production rule grammars
        to set the precedence."""
        return cls.prod_rule_funs["Prec"](cls, arg)

def token_subclass_factory():
    """This function is called from the `create_token_subclass` method of
    `TokenTable` when it needs to create a new subclass to begin
    with.  It should not be called directly.

    Create and return a new token subclass which will be modified and used
    to represent a particular kind of token.  Specifically, each scanned token
    matching the regex defined for tokens with a given token label is
    represented as an instance of the subclass created by calling this function
    (with further attributes, such as the token label, added to it).

    Using a separate subclass for each token label allows for attributes
    specific to a kind of token (including head and tail handler methods) to
    later be added to the class itself without conflicts.  This function
    returns a bare-bones subclass without any head or tail functions, etc."""

    class TokenSubclass(TokenSubclassMeta("TokenSubclass", (object,), {}), TokenNode):
    #class TokenSubclass(TokenNode, metaclass=TokenSubclassMeta):  # Python 3
    #class TokenSubclass(TokenNode):                               # No metaclass.
        """The factory function returns this class to represent tokens.  It is a
        subclass of the `TokenNode` class, defined in the lexer module."""
        static_prec = 0 # The prec value for this kind of token, with default zero.
        token_label = None # Set to the actual value later, by create_token_subclass.
        #parser_instance = None # Set by recursive_parse. AVOID if not needed.

        def __init__(self, value):
            """Initialize an instance of the subclass for a token of the kind
            labeled with `token_label`.  The `value` is the actual parsed
            string from the text.  This instance represents the token."""
            super(TokenSubclass, self).__init__() # Call base class __init__.
            self.value = value # Set from lex.token_generator; static value=None.

            # The `expanded_formal_sig` attr is set upon parsing.  It is the
            # expanded form of one of the formal sigs which were registered
            # with the token (the expansion handles wildcards, repeat options,
            # etc.)  It is the signature which matched the actual args.  The
            # `self.expanded_formal_sig` has an attribute `original_formal_sig`
            # which is the original, unexpanded formal signature that matched
            # (after expansion) the actual arguments.  After parsing it is set
            # as the token attribute `original_formal_sig`.  This is important
            # because the `eval_fun` and `ast_data` for tokens are saved in
            # dicts keyed by the original signature at the time when they are
            # defined (via `modify_token`).  So we need the resolved original
            # signature to look up the value.  (Note that if overloading on
            # return types is turned off then these dicts are keyed only on the
            # argument portion of the original typesig.)
            self.original_formal_sig = "Unresolved" # The matching orig sig.
            self.expanded_formal_sig = "Unresolved" # Expanded version of above.
            self.actual_sig = "Unresolved" # The actual signature.

        @classmethod
        def prec(cls):
            """Return the precedence for the token.  This is currently a static
            value for each type of token.  Later it may be dynamic value
            associated with the particular tail function which is selected in a
            given context. Update: may become an attribute of a construct and
            no longer of a token."""
            return cls.static_prec

        def process_not_in_tree(self):
            """Removes any immediate children which have `not_in_tree` set."""
            modified_children = []
            for child in self.children:
                if not hasattr(child, "not_in_tree"):
                    modified_children.append(child)
                else:
                    modified_children += child.children
            self.children = modified_children

        def process_and_check_node(self, construct,
                                   val_type_override=None, all_vals_override=None,
                                   typesig_override=None):
            """This routine is automatically called just after a handler
            function returns a subtree.  It is called for the root of the
            returned subtree.  It sets some attributes and checks that the
            actual types match some defined type signature for the function.

            If `val_type_override` is set to a `TypeObject` instance then the
            return type of both the `expanded_formal_sig` and the `actual_sig`
            for the node is set to that type *after* the first pass of
            processing and type-checking for the subtree is finished.  (This
            option does not currently work for two-pass checking when
            overloading on return types is used.)  This option is useful for
            handling things like parentheses and brackets which inherit the
            type of their child (assuming the parens and brackets are kept as
            nodes in the parse tree and not eliminated).  The override value is
            used for type-checking farther up the expression tree.

            If `all_vals_override` is set to a `TypeObject` instance then all
            the possible signatures have their `val_type` changed to that type
            *before* any checking is done.  This should work for both one and
            two-pass checking, but no check is made for producing duplicate
            types due to the `val_type` changes.

            The `typesig_override` argument must be a `TypeSig` instance.  If
            set it will be *assigned* to the node as its only possible
            `expanded_formal_sig` before type checking (instead of looking up
            the registered ones).  Type checking then proceeds as usual."""

            # Get all the sigs registered for the node's construct.
            if typesig_override is not None:
                all_possible_sigs = [typesig_override]
            else:
                all_possible_sigs = construct.original_sigs
            if all_vals_override:
                all_possible_sigs = [TypeSig(all_vals_override, s.arg_types)
                                                      for s in all_possible_sigs]
            self.all_possible_sigs = all_possible_sigs # Temporary attribute.

            # Do the actual checking.
            if not self.parser_instance.overload_on_ret_types: # One-pass.
                self._check_types_one_pass()
            else: # Two-pass.
                self._check_types_first_of_two_passes()
                # If we have a *unique* matching sig, run pass two on the
                # subtree.  In this case, since the signature is fixed by
                # argument types (regardless of where the top-down pass
                # starts from) we can in this case resolve the types in the
                # subtree early.  Note `check_types_in_tree_second_pass` is
                # also called on the root node from the `parse` method.
                if len(self.matching_sigs) == 1: # matching_sigs set by _check_types
                    self.check_types_in_tree_second_pass()

            # Implement val_type override if set.
            if val_type_override:
                # Note that the original_formal_sig attribute was already set.
                # The ast_data and eval_fun are keyed on that.
                self.expanded_formal_sig = TypeSig(val_type_override,
                                                   self.expanded_formal_sig.arg_types)
                self.actual_sig = TypeSig(val_type_override, self.actual_sig.arg_types)

        def _check_types_one_pass(self):
            """Utility function called from `process_and_check_node` to check
            the actual types against their signatures when overloading is only on
            argument types."""
            all_possible_sigs = self.all_possible_sigs

            # One-pass, each child c has a unique c.expanded_formal_sig already set.
            list_of_child_sig_lists = [[c.expanded_formal_sig] for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)
            # Below all_possible_sigs is saved ONLY for printing error messages.
            self.all_possible_sigs = all_possible_sigs

            # No overloading on return types so we can finalize the actual types.
            if len(self.matching_sigs) != 1:
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution: The actual argument types match"
                        " multiple signatures.")

            # Found a unique signature; set the node's expanded_formal_sig attribute.
            # Saved sig used for eval_fun resolution, ast_data, semantic action, etc.
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type,
                                      [c.actual_sig.val_type for c in self.children])

            # Delete some temporary attributes no longer needed.
            delattr(self, "matching_sigs")
            delattr(self, "all_possible_sigs")

        def _check_types_first_of_two_passes(self):
            """Utility function called from `process_and_check_node` to do the
            first pass in checking the actual types against their signatures.
            Two-pass checking is needed for overloading on return types.  First
            pass goes up the tree, second pass goes back down."""
            all_possible_sigs = self.all_possible_sigs

            # First pass case, multiple sigs in child's self.matching_sigs list.
            list_of_child_sig_lists = [c.matching_sigs for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)

        def check_types_in_tree_second_pass(self, root=False):
            """Recursively run the second pass on the token subtree with the
            `self` node as the root.

            This method currently still needs to be explicitly called for the
            root of the final parse tree, from the `PrattParser` method
            `parse`, as well as from the checking routines here to do partial
            checks on subtrees which are already resolvable."""
            unresolved_children = [
                    c for c in self.children if hasattr(c, "matching_sigs")]
            self._check_types_pass_two() # Call first on self to do top-down.
            for child in unresolved_children: # Recurse on unprocessed children.
                child.check_types_in_tree_second_pass()
            # Delete childrens' matching_sigs lists after they are no longer needed.
            # This also acts as an indicator that the node has been resolved.
            for child in unresolved_children:
                delattr(child, "matching_sigs")
            if root:
                # The final pass in _check_types that deletes these attrs doesn't get
                # run on root, so it is explicitly done here when `root` flag is true.
                delattr(self, "matching_sigs")
                delattr(self, "all_possible_sigs")

        def _check_types_pass_two(self):
            """A second pass is only used when overloading on return types is
            allowed.  It is a top-down pass where each node chooses a unique
            final signature for each of its children.  It depends on the
            node attribute `self.matching_sigs` having been set in the first
            pass."""
            # On FIRST pass: on the way *up* the tree (after getting the
            # literal tokens, the leaves of the tree) get all the signature
            # types for a node which match in arguments for *some* possible
            # return-type choice of the children.  Same as the one-pass
            # version, but now sets of possibilities are allowed and state is
            # saved for the second pass to use: the list of matching sigs is
            # temporarily saved with the node in the self.matched_sigs
            # attribute.
            #
            # Summary: first pass, bottom-up, find all sigs that match possible
            # val_types of the node's children, across all arguments.
            #
            # After the first pass the root should have a unique sig; if not
            # there is ambiguity.  (Each node saved a set of sigs that is
            # satisfiable by some realizable choice of child sigs, and parents
            # can force children to assume any of their possible types).
            #
            # On SECOND pass: On the way *down* the tree, parents choose one
            # sig as final for each child and set it in that child's node as
            # the new self.matching_sigs.  This should always be a unique sig;
            # otherwise there is ambibuity.  Recursively called on children.
            #
            # Summary: second pass, top-down, root is unique and parents assign
            # and set the (unique) signature for each of their children.
            #
            # Note that this algorithm works just as well if the second pass is
            # run on each subtree as soon as the subtree root has a unique
            # signature, and the recursion only goes down to subtrees with
            # roots having a unique signature.  This yields partial results and
            # some error conditions sooner, and is what is implemented here.

            if len(self.matching_sigs) != 1: # The root case needs this.
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution (second pass).  Possible type "
                        "assignments for the children/arguments of the token node match"
                        " {0} possible node signatures: {1}.  Uniqueness is required."
                        .format(len(self.matching_sigs), self.matching_sigs))

            # We have a unique signature; set the node's type attributes
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            # Start setting the actual signature; children will fill arg types
            # when resolved.
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type, [])

            # Set the actual_sig arg_type for the parent (appending in sequence with others).
            if self.parent is not None:
                parent_args_so_far = list(self.parent.actual_sig.arg_types)
                parent_args_so_far.append(self.expanded_formal_sig.val_type)
                self.parent.actual_sig = TypeSig(self.parent.actual_sig.val_type,
                                                 parent_args_so_far)

            # Update the matching_sigs attribute for each child (should be singleton).
            for count, child in enumerate(self.children):
                if not hasattr(child, "matching_sigs"):
                    continue # Already resolved.
                matched_sigs = TypeSig.get_child_sigs_matching_return_arg_type(
                                      child, self.expanded_formal_sig.arg_types[count],
                                      child.matching_sigs)
                # From the first pass, we know at least one child sig matches.
                assert len(matched_sigs) != 0 # Debug.
                if len(matched_sigs) > 1:
                    # Recursion could catch this on the next step, but better err msg.
                    child._raise_type_mismatch_error(matched_sigs,
                        "Token node has multiple signatures with return type matching "
                        "type of parent (pass two). Parent expects type '{0}'.  Defined"
                        " signatures are: {1}."
                        .format(self.expanded_formal_sig.val_type, child.matching_sigs))
                child.matching_sigs = matched_sigs
            return

        def _raise_type_mismatch_error(self, matching_sigs, basic_msg):
            """Raise an error, printing a helpful diagnostic message.  Assumes
            that `_check_types` has been called (to set `self.all_possible_sigs`)."""
            # TODO: Will the self.expanded_formal_sig *ever* be resolved when this routine is
            # called?  If not, then it is not very useful and message could be reworded.
            diagnostic = ("  The current token has value '{0}' and label '{1}'.  "
                         " Its expanded formal signature is {2}.  The"
                         " children/arguments have token labels and values of {3} and "
                         "value types {4}.  The list of matching signatures "
                         "is {5}.  The list of possible signatures was {6}"
                         .format(self.value, self.token_label,
                             self.expanded_formal_sig,
                             list(c.summary_repr() for c in self.children),
                             # Note this below can be "Unresolved", better message?
                             list(c.expanded_formal_sig.val_type
                                  if not isinstance(c.expanded_formal_sig, str)
                                  else c.expanded_formal_sig for c in self.children),
                             matching_sigs, self.all_possible_sigs))
            raise TypeErrorInParsedLanguage(basic_msg + diagnostic)

        #
        # Evaluations and semantic actions.
        #

        @property
        def eval_fun(self):
            """Return the evaluation function saved with the winning construct
            dispatched for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_eval_fun(orig_sig, token_value_key=self.value)

        @property
        def ast_data(self):
            """Return the ast data saved with the winning construct dispatched
            for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_ast_data(orig_sig, token_value_key=self.value)

        def eval_subtree(self):
            """Run the saved evaluation function on the token, if one was
            registered with it.  Returns `None` if no evaluation function is found."""
            orig_sig = self.original_formal_sig # Set during parsing.
            eval_fun = self.eval_fun # Property method above.

            # TODO: Consider if returning None is better than raising exception...
            if not eval_fun:
                return None

            # TODO: Consider if special exception should be raised.
            #if not eval_fun:
            #    raise ParserException("An evaluation function is needed for token with "
            #            "value '{0}' and label '{1}' but no defined and matching "
            #            "evaluation function was found in the dict of eval functions.  "
            #            "The resolved original signature is {2} and the resolve expanded"
            #            " signature is {3}.  The resolved construct_label is {4}.  The "
            #            "token's eval_fun_dict is:\n   {5}."
            #            .format(self.value, self.token_label, orig_sig, sig,
            #                    self.construct_label, self.eval_fun_dict))

            return eval_fun(self)

        #
        # The main recursive_parse function.
        #

        def get_jop_token_instance(self, lex, processed_left, extra_data, subexp_prec):
            """Returns an instance of the jop token iff one should be inferred in the
            current context; otherwise returns `None`."""
            # TODO: extra_data arg now holds subexp_prec as field.
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler

            # Not if jop token is undefined for the parser.
            if not parser_instance.jop_token_subclass:
                return None

            # Not if at end of expression.
            if lex.peek().is_end_token():
                return None

            # Not if the ignored token for jop is set but not present.
            if parser_instance.jop_ignored_token_label and (
                          parser_instance.jop_ignored_token_label
                          not in lex.peek().ignored_before_labels()):
                return None

            # Now infer a jop, but only if 1) its prec would satisfy the while loop
            # in `recursive_parse` as an ordinary token, 2) the next token has
            # a head handler defined in the conditions when the jop will need
            # to run its head handler, and 3) the next token similarly has no
            # tail handler in the context.
            if parser_instance.jop_token_subclass.prec() > subexp_prec:
                # Provisionally infer a jop; create a subclass instance for its token.
                #
                # Todo: Maybe for jop and null-string tokens define methods
                # get_jop_token_instance() which gets the token but calls the
                # lexer to dress it up more like a "real" token, with ignored_before
                # and line numbers, etc. (without putting it in the buffer, of course).
                jop_instance = parser_instance.jop_token_subclass(None)
                jop_instance.extra_data = extra_data

                # This is a little inefficient (since it uses a `go_back` call)
                # but we need to be sure that when the tail handler of the jop
                # is called and it reads a token that that token has a head
                # handler defined for it *in that precondition context*.
                # Otherwise, no jop will be inferred.  We also make sure that
                # it has no tail handler in the context, since then it would be
                # a lower-precedence (lower precedence because we broke out of
                # the loop above) infix or postfix operator, and no jop is
                # inferred before another operator).
                curr_token = lex.next()
                try:
                    # Dispatch here WITHOUT CALLING, since calling will consume
                    # another token; also, deeper-level recursions could cause false
                    # results to come up the recursion chain.  We are just testing
                    # what handlers are defined for the token.
                    _peek_head_handler, head_construct = dispatch_handler(
                                                   HEAD, curr_token, lex, extra_data)
                    try: # Found head handler, now make sure it has no tail handler.
                        _peek_tail_handler, tail_construct = dispatch_handler(
                                   TAIL, curr_token, lex, extra_data, processed_left)
                    except NoHandlerFunctionDefined:
                        # This is the only case where an actual token is returned.
                        return jop_instance
                    else:
                        return None
                except NoHandlerFunctionDefined:
                    return None # No precondition matches, assume no jop.
                finally:
                    #delattr(curr_token, "extra_data") # Only needed if pushback below, not go_back.
                    lex.go_back(1)
            else:
                return None

        def dispatch_null_string_handler(self, head_or_tail, lex, subexp_prec,
                                         extra_data, processed_left=None):
            """Check for any possible matching null-string token handlers;
            return the token and the matching handler if one is found.

            Note that the precedence for a null-string token is set to
            `subexpr_prec`, so it would always have activated the while loop if
            it were a real token."""
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            # See if a null-string token is set and a handler matches preconds.
            if not parser_instance.null_string_token_label:
                return None, None, None
            else:
                # TODO: Later don't re-create each time, save one.
                null_string_token = parser_instance.null_string_token_subclass(None)
            null_string_token.extra_data = extra_data

            curr_token = None
            handler_fun = None
            construct = None
            try:
                handler_fun, construct = dispatch_handler(head_or_tail,
                                                          null_string_token,
                                                          lex, extra_data, processed_left)
                curr_token = null_string_token
            except NoHandlerFunctionDefined:
                pass
            return curr_token, handler_fun, construct

        def recursive_parse(self, subexp_prec, only_head=False):
            """Parse a subexpression as defined by token precedences. Return
            the result of the evaluation.  Recursively builds up the final
            result in `processed_left`, which is the tree for the part of the
            full expression to the left of the current token.

            The list `lookbehind` saves all the previously evaluated
            subexpressions at this level of recursion (i.e., at the top level
            in the same subexpression) and passes it to the dispatched tail
            handlers, in case that routine wants to make use of it.  For
            example, the ordinal position of the token in the top level of the
            subexpression can be calculated from the length of `lookbehind`.

            This function is made a method of `TokenSubclass` so that handler
            functions can easily call it by using `tok.recursive_parse`, and
            also so that it can access the lexer without it needing to be
            passed as an argument.  It is basically a static function,
            though.

            The `extra_data` attribute is set for all triggering tokens, and is
            guaranteed to be available for precondition functions and for
            handler functions.  It is set before any dispatches or recursive calls,
            and is deleted from the token after the recursive call.  It is an
            advanced feature which most users will not need."""
            # Note that all the dispatching functions set the `extra_data`
            # attribute of their token before the dispatching is done, but they
            # do not update `extra_data` itself in any way.

            # Note on below code: It is tempting for efficiency to define a jop
            # and null-string token instance, save it, and only use it when
            # necessary (replacing it only when used).  But some things need to
            # be considered.
            #
            # Now that handlers are not with tokens, that is no longer a
            # concern... TODO go ahead and do this.
            #
            # Is there any special attribute or other thing that is assigned on
            # creation which might change?  Either way, you should probably add
            # extra things like line numbers to mimic ordinary tokens. Note
            # that currently you only really pay the creation cost if you
            # actually use the jop or null-string feature, but a lot of dummy
            # instances are created if you do.

            # This err check catches some cases of tokens defined via Lexer, not all.
            if not hasattr(self, "token_kind"):
                raise ParserException("All tokens used in the parser must be"
                        " defined in via parser's methods, not the lexer's.")

            #
            # Initialize, and set some shorter aliases.
            #

            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            lex = self.token_table.lex
            extra_data = ExtraDataTuple(lookbehind=[], constructs=[],
                                        subexp_prec=subexp_prec)

            #
            # Start the actual Pratt parsing recursion.
            #

            curr_token, head_handler, construct = self.dispatch_null_string_handler(
                                                     HEAD, lex, subexp_prec, extra_data)
            if not curr_token: # No null-string token fired, so use normal next() call.
                curr_token = lex.next()
                head_handler, construct = dispatch_handler(
                                                     HEAD, curr_token, lex, extra_data)

            extra_data.constructs.append(construct)

            # TODO: Should the root of processed_left be set for is_head instead, for
            # general case?  Or set "head_trigger_token" to label instead of None?
            # Consider how lookup will work in usual and general cases of arbitrary
            # token as subtree root.
            curr_token.is_head = True # Used to look up eval_fun and ast_data later.

            processed_left = head_handler()

            delattr(curr_token, "extra_data") # Delete after recurse, allow mem cleanup.
            extra_data.lookbehind.append(processed_left)
            extra_data.constructs.append(construct)

            if only_head:
                return processed_left

            while True:

                #
                # The loop below is the main loop in ordinary Pratt parsing.  The
                # Outer loop is ONLY for the special case when a jop is defined.
                #

                # TODO: Consider modification like code below to allow
                # precedences per constuct, which also makes "prec - 1" no
                # longer necessary for right assoc when property is set for the
                # construct itself.  See what performance hit it has, one
                # go_back per subexpression.  Note that jops use a single
                # go_back already when they are defined...
                #
                # The ugly comment-string code below works.  It just pulls the
                # token-dispatching out to before the precedence test.
                # Obviously could then use some cleanup and refactoring, too.
                # Consider possible interactions with jop and null-string
                # tokens, but they don't do a `next` call anyway.  (Is it
                # better to pull out the ns_token dispatch, at least?  In
                # regular code, how to get null-string to appear at end of a
                # subexpression?)
                #
                # Argument it works: This code is doing exactly the same
                # dispatching as it would inside the loop test, but it is doing
                # it before the loop test.  The loop test never modifies
                # anything.  If the test fails the effects of the dispatches
                # are undone.
                """
                while True:
                    #err = None
                    ns_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if ns_token:
                        curr_token = ns_token
                        peek_prec = lex.token.prec()
                        #peek_prec = construct.prec() # Switch to this...
                    else:
                        curr_token = lex.next()
                        try:
                            tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                            lex, extra_data, processed_left)
                            peek_prec = lex.token.prec()
                            #peek_prec = construct.prec() # Switch to this...
                        except NoHandlerFunctionDefined as e:
                            # If no construct at all then can't have tail handler so
                            # prec should be 0.  But if it fails due to a precond,
                            # token itself could still have a prec > 0.  In that case
                            # it will get inside the loop and fail, but it really
                            # shouldn't have gotten inside.
                            #
                            # Only one test changes, and new one is commented out in
                            # the test file under the old one.
                            #err = e
                            peek_prec = -1 # Always fail test and break.
                            #peek_prec = lex.token.prec()

                    #test_assoc = False if err else (peek_prec == subexp_prec and
                    #                                construct.assoc == "right")
                    test_assoc = peek_prec == subexp_prec and construct.assoc == "right"
                    if peek_prec > subexp_prec or test_assoc:
                        #if err: # Error would have been found inside loop, now above.
                        #    raise err # Avoid error msg changing (makes test fail).
                        processed_left = tail_handler()
                        delattr(curr_token, "extra_data")
                        extra_data.lookbehind.append(processed_left)
                        extra_data.constructs.append(construct)
                    else:
                        if not ns_token:
                            lex.go_back(1)
                        break
                """

                while lex.peek().prec() > subexp_prec:

                    curr_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if not curr_token: # No null handler fired off, get regular way.
                        curr_token = lex.next()
                        tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                        lex, extra_data, processed_left)

                    processed_left = tail_handler()
                    delattr(curr_token, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)

                #
                # Broke out of main loop, determine whether or not to infer a jop.
                #

                jop_instance = self.get_jop_token_instance(
                                         lex, processed_left, extra_data, subexp_prec)
                if jop_instance:
                    jop_tail_handler, construct = dispatch_handler(TAIL, jop_instance,
                                                        lex, extra_data, processed_left)
                    processed_left = jop_tail_handler()
                    delattr(jop_instance, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)
                else:
                    break

            return processed_left

        #
        # Copying instances of tokens.
        #

        def __copy__(self):
            """Return a shallow copy of the token."""
            return copy.copy(self)

        #
        # Some representations that apply to the subclasses.
        #

        def summary_repr_with_types(self):
            """A short summary repr of the node, without its children."""
            return ("<" + str(self.token_label) +
                    ",'" + str(self.value) +
                    "'," + str(self.expanded_formal_sig.val_type) + ">")

        def tree_repr_with_types(self, indent=""):
            """Token representation as the root of a parse subtree, with formatting.
            The optional `indent` parameter can be either an indent string or else
            an integer for the number of spaces to indent.  Note that the ordinary
            `tree_repr` method without types is also available, inherited from
            the base node object."""
            try:
                num_indent = int(indent)
            except ValueError:
                pass
            else:
                indent = " " * num_indent
            string = indent + self.summary_repr_with_types() + "\n"
            for c in self.children:
                string += c.tree_repr_with_types(indent=indent+" "*4)
            return string

        def string_repr_with_types(self):
            """A string repr for the tree that includes type information."""
            string = self.summary_repr_with_types()
            if self.children:
                string += "("
                string += ",".join(c.string_repr_with_types() for c in self.children)
                string += ")"
            return string

        @classmethod
        def class_repr(cls):
            """Print out the `TokenSubclass` classes (representing tokens) in a
            nice way.  The default is hard to read."""
            string = "Token({0})".format(cls.token_label)
            return string

    return TokenSubclass # Return from token_subclass_factory function.

#
# Parser
#

def lexer_add_parser_instance_attribute(lexer, token):
    """Passed to lexer to add a `parser_instance` attribute to each token it
    returns.  This attribute is added to instances at the lexer, from its
    current token table, because of the case where parsers call other parsers.
    (It is not added to general token subclasses in `def_token_master` because
    parsers could potentially share token subclasses.)"""
    token.parser_instance = lexer.token_table.parser_instance # From token table.
    return token

# Could also add parser_instance and construct as fields of the extra data tuple.
# Could extra_data also be passed to handler functions?  Nice to have construct
# instance available there, perhaps.  TODO: Consider.
ExtraDataTuple = namedtuple("ExtraHandlerData", ["lookbehind",
                                                 "constructs",
                                                 "subexp_prec"])

class PrattParser(object):
    """A parser object.  Each parser object contains a table of defined tokens,
    a lexer, a table of constructs, and a table of defined types."""
    def __init__(self, max_peek_tokens=None,
                       max_deque_size=None,
                       lexer = None,
                       default_begin_end_tokens=True,
                       type_table = None,
                       skip_type_checking=False,
                       overload_on_arg_types=True,
                       overload_on_ret_types=False,
                       partial_expressions=False,
                       parser_label=None,
                       raise_on_equal_priority_preconds=False):
        """Initialize the parser.

        The `max_peek_tokens` parameter is an optional arbitrary limit on the
        level of peeks allowed in the lexer.  Setting to 1 limits it to a
        single token lookahead.  The default setting `None` gives
        peek-on-demand as far ahead as requested.

        The `max_deque_size` parameter is an optional limit on the size of the
        deque that the lexer keeps for previous tokens, the current token, and
        requested peek tokens.  The default is for it to grow arbitrarily
        (though it is reset on each parse).  Needs to be large enough for the
        max level of peeks required plus the max `go_back` level required.

        If a `Lexer` instance is passed in the parser will use that lexer and
        its token table, otherwise a new lexer is created.  The any other lexer
        options are ignored.

        No default begin and end functions will be set if a lexer is passed in,
        regardless of the value of `default_begin_end_tokens`.  Otherwise,
        default begin and end tokens will be defined unless
        `default_begin_end_tokens` is set false (note that creating them by
        default is the opposite of the default behavior for the lower-level
        Lexer class).

        Setting `skip_type_checking=True` is slightly faster since typing is
        not being used at all.  Note that overloading depends on type-checking
        to resolve the actual types, so this flag implies that the overload
        flags are all false.  The default is false.  It should be possible to
        define types, use them during testing, and then turn checking off ---
        provided overloading is not used to get different evaluation functions
        or AST data elements for different overloads.

        The `overload_on_arg_types` flag specifies whether or not to overload
        on argument types.  The default is true.  Cannot be changed after
        initialization.

        Setting `overload_on_ret_types` also overloads on argument types.  It
        requires an extra walk of the token tree, and implies overloading on
        argument types.  The default is false.  Cannot be changed after
        initialization.

        If `partial_expressions` is set true then no check will be made in the
        `parse` method to see if the parsing consumed up to the end-token in
        the lexer.  Multiple expression text can be parsed by repeatedly
        calling `parse` when this option is true and checking whether the
        lexer's current token is the end-token.

        The `parser_label` is an optional descriptive string for a parser.
        These can be useful in debugging when they appear in error messages,
        especially when working with multiple parser instances.

        If `raise_on_equal_priority_preconds` is true then an exception will be
        raised if two precondition functions are registered with the same
        trigger token in the same head or tail position which have the same
        precondition priority.  The default is false, and the first-defined
        matching precondition function of the same priority will win any
        competition when several are true.  This option can be used to ensure
        at language define-time that there is no definition-order dependence in
        dispatching.  If two such preconditions functions are mutually
        exclusive there is no problem with them having the same priority, but
        this condition cannot be checked by a program.  A small difference can
        be added."""

        if parser_label:
            self.parser_label = parser_label # Set first, for error messages.
        else:
            self.parser_label = None

        ## Type-checking options below; these cannot be changed after initialization.
        if overload_on_ret_types:
            overload_on_arg_types = True # Overload on ret implies overload on args.
        self.skip_type_checking = skip_type_checking # Skip all type checks, faster.
        if not skip_type_checking:
            self.overload_on_arg_types = overload_on_arg_types
            self.overload_on_ret_types = overload_on_ret_types
        else: # Overloading requires type checking.
            self.overload_on_arg_types = False
            self.overload_on_ret_types = False

        # If exceptions are not raised on ties then with non-mutually-exclusive
        # precond functions the first-set one will have precedence when they
        # are both true.  Need to define this before registering any handlers (
        # which is done below in `def_begin_end_tokens`).
        self.raise_on_equal_priority_preconds = raise_on_equal_priority_preconds
        #self.raise_on_equal_priority_preconds = True # DEBUG

        self.construct_table = ConstructTable(parser_instance=self) # Dict of constructs.
        self.default_construct_label_number = 0 # For unique precondition labels.

        if lexer: # Lexer passed in.
            self.lex = lexer
            self.token_table = lexer.token_table
        else: # No Lexer passed in.
            self.token_table = TokenTable(
                                token_subclass_factory_fun=token_subclass_factory)
            self.lex = Lexer(self.token_table,
                             max_peek_tokens=max_peek_tokens,
                             max_deque_size=max_deque_size,
                             default_begin_end_tokens=False)
            # Set the begin and end tokens unless the user specified not to.
            if default_begin_end_tokens:
                self.def_begin_end_tokens() # Use function's defaults.
        self.lex.default_helper_exception = ParserException # Default for match_next, etc.
        # Add mod function to lexer here, works even if they passed in a lexer.
        self.lex.final_mod_function = lexer_add_parser_instance_attribute

        self.token_table.parser_instance = self # Give token table ref to parser.

        if type_table:
            self.type_table = type_table
        else:
            self.type_table = TypeTable(self)

        self.num_lookahead_tokens = max_peek_tokens
        self.jop_token_label = None # Label of the jop token, if any.
        self.jop_token_subclass = None # The actual jop token, if defined.
        self.null_string_token_label = None # Label of the null-string token, if any.
        self.null_string_token_subclass = None # The actual null-string token, if any.

        self.partial_expressions = partial_expressions # Whether to parse multiple expressions.

        self.pstate_stack = [] # Stack of production rules used in grammar parsing.
        self.top_level_production = False # If true, require grammar parses to consume to end.
        self.disable_pstate_processing = False # Set to temporarily disable grammar parsing.

    #
    # Methods defining tokens.
    #

    def def_token_master(self, token_label, regex_string=None, on_ties=0, ignore=False,
                         token_kind="regular", ignored_token_label=None,
                         matcher_options=None):
        """The master method for defining tokens; all the convenience methods
        actually call it.  Allows for factoring out some common code and
        keeping the attributes of all the different kinds of tokens up-to-date.
        This routine calls the underlying lexer's `def_token` to get tokens and
        then adds extra attributes needed by the `PrattParser` class.

        The `token_kind` argument must be one of the following strings:
        `"regular"`, `"ignored"`, `"begin"`, `"end"`, `"jop"`, or
        `"null-string"`.  The `ignored_token_label` is used only when defining
        a jop.

        Tokens can be shared between parsers if all their properties are the
        same.  Note that for now this includes the precedence value for any
        tail handlers (since that is made a token attribute).  Null-string and
        jop tokens are the exception, but they are special in that they are
        never returned by the lexer, only by a particular parser."""
        token_table = self.token_table

        if token_kind == "regular":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=ignore, matcher_options=matcher_options)

        elif token_kind == "ignored":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=True, matcher_options=matcher_options)

        elif token_kind == "begin":
            tok = token_table.def_begin_token(token_label)
            self.begin_token_label = token_label
            # Define dummy handlers for the begin-token, just to catch errors.
            def begin_head(self, lex):
                """Dummy head handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called head-handler for begin token.")
            def begin_tail(self, lex, left):
                """Dummy tail-handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called tail-handler for begin token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, begin_head, token_label)
            self.def_construct(TAIL, begin_tail, token_label, dummy_handler=True)
            self.begin_token_subclass = tok

        elif token_kind == "end":
            tok = token_table.def_end_token(token_label)
            self.end_token_label = token_label
            # Define dummy handlers for the end-token, just to catch errors.
            def end_head(self, lex):
                """Dummy head handler for end-tokens."""
                raise CalledEndTokenHandler("Called head-handler for end token.")
            def end_tail(self, lex, left):
                """Dummy tail-handler for end-tokens."""
                raise CalledEndTokenHandler("Called tail-handler for end token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, end_head, token_label)
            self.def_construct(TAIL, end_tail, token_label, dummy_handler=True)
            self.end_token_subclass = tok

        elif token_kind == "jop":
            if self.jop_token_subclass:
                raise ParserException("A jop token is already defined.  It must be "
                                      "undefined before defining a new one.")
            self.jop_token_label = token_label
            self.jop_ignored_token_label = ignored_token_label
            tok = token_table.def_token(token_label, None)
            self.jop_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        elif token_kind == "null-string":
            if self.null_string_token_subclass:
                raise ParserException("A null-string token is already defined.  It"
                         " must be undefined before defining an new one.")
            self.null_string_token_label = token_label
            tok = token_table.def_token(token_label, None)
            self.null_string_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        else:
            raise ParserException("Bad call to def_token_master, with unrecognized"
                    ' string "{0}" for the keyword argument token_kind.'
                    .format(token_kind))

        tok.token_kind = token_kind
        tok.is_head = False # Set true in recursive_parse if instance parses as a head.
        return tok

    def def_token(self, token_label, regex_string, on_ties=0, ignore=False,
                  matcher_options=None):
        """Define a token.  Use this instead of the Lexer `def_token` method,
        since it adds extra attributes to the tokens."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore,
                              token_kind="regular", matcher_options=matcher_options)

    def def_ignored_token(self, token_label, regex_string, on_ties=0,
                          matcher_options=None):
        """A convenience function to define a token with `ignored=True`."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore=True,
                              token_kind="ignored", matcher_options=matcher_options)

    def def_begin_end_tokens(self, begin_token_label="k_begin",
                                   end_token_label="k_end"):
        """Calls the `Lexer` method to define begin- and end-tokens.  The
        subclasses are then given initial head and tail functions for use in
        the Pratt parser.  To use the `PrattParser` this method must be called,
        not the method of `Lexer` with the same name (since it also creates
        head and tail handler functions that raise exceptions for better error
        messages).  The default is to call this method automatically on
        initialization, with the default token labels for the begin and end
        tokens.  If the flag `default_begin_end_tokens` is set false on
        `PrattParser` initalization then the user must call this function
        (setting whatever token labels are desired).  Returns a tuple
        containing the new begin and end `TokenNode` subclasses."""
        begin_tok = self.def_token_master(begin_token_label, token_kind="begin")
        end_tok = self.def_token_master(end_token_label, token_kind="end")
        return begin_tok, end_tok

    def def_jop_token(self, jop_token_label, ignored_token_label):
        """Define a token for the juxtaposition operator.  This token has no
        regex pattern.  An instance is inserted in `recursive_parse` when it is
        inferred to be present.  This method must be explicitly called before a
        juxtaposition operator can be used (i.e., before `def_jop`).  The
        parameter `jop_token_label` is the label for the newly-created token
        representing the juxtaposition operator.  The `ignored_token_label`
        parameter is the label of an ignored token which must be present for a
        jop to be inferred.  Some already-defined token is required; usually it
        will be a token for spaces and tabs.  If set to `None` then no ignored
        space at all is required (i.e., the operands can be right next to each
        other)."""
        return self.def_token_master(jop_token_label,
                                     ignored_token_label=ignored_token_label,
                                     token_kind="jop")

    def def_null_string_token(self, null_string_token_label="k_null-string"):
        """Define the null-string token.  This token has no regex pattern.  An
        instance is inserted in `recursive_parse` when it is inferred to be
        present based.  This method must be called before a
        null-string can be used.  The parameter `null_string_token_label` is
        the label for the newly-created tok representing it."""
        return self.def_token_master(null_string_token_label,
                                     token_kind="null-string")

    def get_token(self, token_label):
        """Return the token with the label `token_label`.  The reverse
        operation, getting a label from a token instance, can be done by
        looking at the `token_label` attribute of the token."""
        return self.token_table[token_label]

    #
    # Undefine tokens.
    #

    def undef_token(self, token_label):
        """A method for undefining any token defined by the `PrattParser` methods.
        Since the `token_kind` was set for all tokens when they were defined
        it knows how to undelete any kind of token."""
        # TODO: Make sure this is up-to-date with the what the token_master class does.
        token_table = self.token_table
        tok = token_table[token_label]
        kind = tok.token_kind
        if kind == "jop":
            token_table.undef_token(self.jop_token_label)
            self.jop_token_subclass = None
            self.jop_token_label = None
            self.jop_ignored_token_label = None
        elif kind == "null-string":
            token_table.undef_token(self.null_string_token_label)
            self.null_string_token_subclass = None
            self.null_string_token_label = None
            self.null_string_ignored_token_label = None
        else:
            token_table.undef_token(token_label)

    #
    # Methods to define and undefine constructs.
    #

    def def_construct(self, head_or_tail, handler_fun, trigger_token_label,
                      prec=0, construct_label=None, precond_fun=None,
                      precond_priority=0, val_type=None, arg_types=None,
                      eval_fun=None, ast_data=None, token_value_key=None,
                      dummy_handler=False):
        """Define a construct and register it with the token with label
        `trigger_token_label`.  A token with that label must already be in the
        token table or an exception will be raised.

        Stores the construct instance in the parser's construct table and also
        return the construct instance.

        The `head_or_tail` argument should be set to either `HEAD` or `TAIL`.
        If `head_or_tail==TAIL` then the operator precedence will be set to
        `prec`.  For a head handler the `prec` value is ignored and effectively
        set to zero.  For a tail handler a `prec` value greater than zero is
        required or else an exception will be raised (unless `dummy_handler` is
        set true).  Similarly, an exception is raised for a non-zero `prec`
        value for a head-handler (the default value).

        The `construct_label` is an optional string value which can result in
        better error messages.

        The `eval_fun` and the `ast_data` arguments are saved in dicts
        associated with the type signature.

        If `token_value_key` is set to a string value then that value will be
        part of the key tuple for saving AST data and evaluation functions.
        This can be used, for example, when overloading a generic identifier
        with different evaluation functions for when the identifier value is
        `sin`, `cos`, etc.  In looking up the AST data and evaluation function
        the parsed token's actual string value (from the program text) is used
        as the key.  If any overload of a particular construct provides a
        `token_value_key` string then all the other overloads for that
        construct must also (for the time being, at least)."""
        # Note that the parser_instance attribute of tokens is not necessarily
        # set yet when this method is called.
        if isinstance(arg_types, str):
            raise ParserException("The arg_types argument to token_subclass must"
                    " be None or an iterable returning type labels (e.g., a list"
                    " or tuple).")

        if head_or_tail == TAIL and prec <= 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a tail hander and a precedence of zero or less."
                    .format(trigger_token_label))
        if head_or_tail == HEAD and prec != 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a head hander and a precedence not equal to zero."
                    .format(trigger_token_label))

        if precond_fun is None:
            precond_fun = DEFAULT_ALWAYS_TRUE_PRECOND_FUN

        if trigger_token_label in self.token_table:
            trigger_token_subclass = self.get_token(trigger_token_label)
        else:
            raise ParserException("In call to def_construct: subclass for"
                    " token labeled '{0}' has not been defined.  Maybe try"
                    " calling def_token first.".format(trigger_token_label))
            # Below line formerly just created a subclass, but that can mask errors!
            #TokenSubclass = self.token_table.create_token_subclass(token_label)

        if not hasattr(trigger_token_subclass, "token_kind"):
            raise ParserException("Token with label '{0}'  must be defined by the"
                                  " parser's def_token method, not the lexer's method."
                                  .format(trigger_token_label))

        # TODO: Precedence is currently saved as a token attribute.  Consider
        # saving it in the construct instead.  See main Sphinx docs, unimplemented
        # generalizations.
        if head_or_tail == TAIL:
            if (trigger_token_subclass.static_prec != 0 and
                    prec != trigger_token_subclass.static_prec):
                raise ParserException("Redefining the precedence of the triggering"
                        " token subclass '{0}' to a new value {1} not equal"
                        " to the previous nonzero value of {2}."
                        " The original precedence will never be used.  To actually"
                        " reset the value, set trigger_token_label.static_prec=0"
                        " explicitly before this call to def_construct.  Currently"
                        " all operators with the same triggering token must have"
                        " the same precedence value, regardless of preconditions."
                        .format(trigger_token_label, prec,
                                trigger_token_subclass.static_prec))
            trigger_token_subclass.static_prec = prec # Ignore prec for heads; will stay 0.

        # Create the type sig object.
        if self.skip_type_checking:
            type_sig = None
        else:
            type_sig = TypeSig(val_type, arg_types)

        # Register the handler funs.
        construct = self.construct_table.register_construct(
                                          head_or_tail=head_or_tail,
                                          trigger_token_subclass=trigger_token_subclass,
                                          handler_fun=handler_fun,
                                          precond_fun=precond_fun,
                                          precond_priority=precond_priority,
                                          construct_label=construct_label,
                                          type_sig=type_sig,
                                          eval_fun=eval_fun,
                                          ast_data=ast_data,
                                          token_value_key=token_value_key)
        return construct

    def undef_construct(self, construct, type_sig=None, token_value_key=None):
        """Undefine a construct.  If `type_sig` is passed a `TypeSig` instance then
        only that overload is deleted.  If `token_value_key` is also defined then
        only that token key is unregistered.  Otherwise the full construct is
        removed from the parser's construct table."""
        # Note users themselves could unregister the overloads if they have the
        # construct instance.
        self.construct_table.unregister_construct(construct, type_sig, token_value_key)

    #
    # Methods dealing with types.
    #

    def def_type(self, type_label):
        """Define a type associated with the name `type_label`."""
        return self.type_table.create_typeobject(type_label)

    def undef_type(self, type_label):
        """Undefine the type associated with the name `type_label`."""
        self.type_table.undef_typeobject(type_label)

    #
    # The main parse routines.
    #

    def parse_from_lexer(self, lexer_to_use, pstate=None):
        """The same as the `parse` method, but a lexer_to_use is already assumed to be
        initialized.  This is ONLY used when one parser instance calls another
        parser instance (implicitly, via the handler functions of its tokens).
        The outer parser calls this routine of the inner, subexpression parser.
        Such a call to another parser would look something like::

            alternate_parser.parse_from_lexer(lexer_to_use)

        where `lexer_to_use` is the lexer_to_use of the outer parser.  This routine
        temporarily swaps the token table for the passed-in lexer_to_use to be the
        token table for this parser (remember that this parser is the inner
        parser when this routine is called)."""
        # Note you do not need to set the type_table, since the tokens always
        # have fixed references to their own parser instance.

        # Set up to read from lexer_to_use, after setting its token table to
        # be the token table for this parser (this is the inner parser).

        # Temporarily change new lexer's token table.
        lexer_to_use_usual_table = lexer_to_use.token_table
        lexer_to_use.set_token_table(self.token_table)

        # Swap the lexer in.
        usual_lexer = self.lex
        self.lex = lexer_to_use # Swap the lexer.

        try:
            parsed_subexpression = self.parse("IGNORED", pstate=pstate,
                                    partial_expressions=True,
                                    skip_lex_setup=True)
        except ParserException:
            print("Error in `parse_from_lexer` method, in call to `parse` method"
                    " using a different parser's lexer for a subexpression.",
                    file=sys.stderr)
            raise
        finally:
            # Restore the temporary lexer's token table.
            lexer_to_use.set_token_table(lexer_to_use_usual_table)
            self.lex = usual_lexer
        return parsed_subexpression

    def parse(self, program, pstate=None, partial_expressions=None,
                                                      skip_lex_setup=False):
        """The main routine for parsing a full program or expression.  Users of
        the class should call this method to perform the parsing operations
        (after defining a grammar, of course).

        Unless there was a parsing failure or `partial_expressions` is true
        then the lexer is left with the end-token as the current token.

        If the `pstate` variable is set then the value will be pushed as the
        initial state on the production rule stack `pstate_stack`.  The stack
        is then cleared after a successful call.  (Set the parser attribute
        directly for more control.)

        The parser's `partial_expressions` attribute will be used unless it is
        overridden by the parameter `partial_expressions` here.  When it is
        true no check is made for the end-token after `recursive_parse` returns
        a value.    The lexer will be left at the last token consumed, so a
        check for the end-token will tell when all the text was consumed.
        Users are responsible for making sure their grammars are suitable for
        this kind of parsing if the option is set.

        If the `skip_lex_setup` parameter is true then the text `program` is
        ignored and lexer setup is skipped.  This is generally ONLY used when
        multiple parsers are parsing from a common text stream, and `parse` is
        called from the method `parse_from_lexer`."""
        if pstate:
            self.pstate_stack = [pstate] # For parsing production rule grammars.
        if partial_expressions is None:
            partial_expressions = self.partial_expressions

        if not skip_lex_setup:
            self.lex.set_text(program)
        begin_tok = self.lex.token # Get the first token to access recursive_parse.
        parse_tree = begin_tok.recursive_parse(0)

        # Finalize type-checking for root when overloading on return types.
        if self.overload_on_ret_types:
            parse_tree.check_types_in_tree_second_pass(root=True)

        # See if we reached the end of the token stream.
        if not self.lex.peek().is_end_token() and not partial_expressions:
            raise IncompleteParseException("Parsing never reached the end of"
                " the text.  Parsing stopped with tokens still in the lexer."
                "  No syntax element was recognized. The last-parsed token had"
                " value '{0}' and label '{1}'.  Parsing stopped before a token"
                " in the lexer with value '{2}' and label '{3}'.  The partial"
                " result returned is:\n{4}"
                .format(self.lex.token.value, self.lex.token.token_label,
                        self.lex.peek().value, self.lex.peek().token_label,
                        parse_tree.tree_repr()))

        if pstate:
            self.pstate_stack = []
        return parse_tree

#
# Copy the convenience functions from builtin_parse_methods to the PrattParser class.
#

for method in builtin_parse_methods.parse_methods:
    setattr(PrattParser, method.__name__, method)

for method in predefined_token_sets.token_defining_methods:
    setattr(PrattParser, method.__name__, method)

#
# Exceptions
#

class IncompleteParseException(ParserException):
    """Only raised at the end of the `PrattParser` function `parse` if tokens
    remain in the lexer after the parser finishes its parsing."""
    pass

class TokenSubclassMeta(type):
    """A trivial metaclass that will actually create the `TokenSubclass`
    objects.  Since tokens are represented by classes, rather than instances,
    this is necessary in order to change their `__repr__` (the defalt one is
    ugly for tokens) and to overload operators to work for token operands
    in the EBNF-like grammar."""
    def __new__(mcs, name, bases, dct):
        new_class = super(TokenSubclassMeta, mcs).__new__(mcs, name, bases, dct)

        # Below is ugly, but avoids mutual import problems.  Used as an easy
        # way to define token addition so that it works in the grammars defined
        # by the ebnf_classes_and_operators module.
        from .ebnf_classes_and_operators import (
                                     Tok, Not, Prec, nExactly, nOrMore, Repeat)
        # These are saved in a dict below because if they are made attributes
        # then Python 2 complains about "TypeError: unbound method Tok() must
        # be called with TokenClass_k_lpar instance as first argument (got
        # TokenSubclassMeta instance instead)".
        new_class.prod_rule_funs = {
                "Tok": Tok,
                "Not": Not,
                "Prec": Prec,
                "nExactly": nExactly,
                "nOrMore": nOrMore,
                "Repeat": Repeat,
                }
        return new_class

    #
    # Define a nicer-looking __repr__, since the classes represent tokens.
    #

    def __repr__(cls):
        """The representation for tokens.  Tokens are commonly used in the
        code but, being classes, have an ugly default `__repr__` when printed out.
        In this metaclass we can define a better `__repr__` for tokens."""
        string = "TokenClass_{0}".format(cls.token_label)
        return string

    #
    # These overloads work with the ebnf_classes_and_operators module.
    #

    # TODO: Could have a flag to turn overloads on and off, maybe.
    # Might want to turn off when not processing a grammar expression
    # using the tokens, but it really shouldn't matter much.
    def __add__(cls, other):
        """Addition of two tokens is defined to simply return a tuple of
        both tokens.  This is so raw tokens can be used in the operator
        overloaded form of defining production rules for a grammar."""
        return cls.prod_rule_funs["Tok"](cls) + other

    def __radd__(cls, left_other):
        """The right version of `__add__` above."""
        return left_other + cls.prod_rule_funs["Tok"](cls)

    def __or__(cls, other):
        """The `|` symbol simply converts this object into an `ItemList`
        and then calls `__or__` for those objects."""
        return cls.prod_rule_funs["Tok"](cls) | other

    def __ror__(cls, left_other):
        """The right version of `__or__` above."""
        return left_other | cls.prod_rule_funs["Tok"](cls)

    def __rmul__(cls, left_other):
        """The expression `n*token` for an int `n` is "n occurrences of"
        `token`."""
        return cls.prod_rule_funs["Repeat"](left_other, cls)

    def __rpow__(cls, left_other):
        """The expression `n**token` for an int `n` is "n or more occurrences of"
        `token`."""
        return cls.prod_rule_funs["nOrMore"](left_other, cls)

    def __invert__(cls):
        """Define the `~` operator for production rule grammars."""
        return cls.prod_rule_funs["Not"](cls)

    def __getitem__(cls, arg):
        """Define the bracket indexing operator for production rule grammars
        to set the precedence."""
        return cls.prod_rule_funs["Prec"](cls, arg)

def token_subclass_factory():
    """This function is called from the `create_token_subclass` method of
    `TokenTable` when it needs to create a new subclass to begin
    with.  It should not be called directly.

    Create and return a new token subclass which will be modified and used
    to represent a particular kind of token.  Specifically, each scanned token
    matching the regex defined for tokens with a given token label is
    represented as an instance of the subclass created by calling this function
    (with further attributes, such as the token label, added to it).

    Using a separate subclass for each token label allows for attributes
    specific to a kind of token (including head and tail handler methods) to
    later be added to the class itself without conflicts.  This function
    returns a bare-bones subclass without any head or tail functions, etc."""

    class TokenSubclass(TokenSubclassMeta("TokenSubclass", (object,), {}), TokenNode):
    #class TokenSubclass(TokenNode, metaclass=TokenSubclassMeta):  # Python 3
    #class TokenSubclass(TokenNode):                               # No metaclass.
        """The factory function returns this class to represent tokens.  It is a
        subclass of the `TokenNode` class, defined in the lexer module."""
        static_prec = 0 # The prec value for this kind of token, with default zero.
        token_label = None # Set to the actual value later, by create_token_subclass.
        #parser_instance = None # Set by recursive_parse. AVOID if not needed.

        def __init__(self, value):
            """Initialize an instance of the subclass for a token of the kind
            labeled with `token_label`.  The `value` is the actual parsed
            string from the text.  This instance represents the token."""
            super(TokenSubclass, self).__init__() # Call base class __init__.
            self.value = value # Set from lex.token_generator; static value=None.

            # The `expanded_formal_sig` attr is set upon parsing.  It is the
            # expanded form of one of the formal sigs which were registered
            # with the token (the expansion handles wildcards, repeat options,
            # etc.)  It is the signature which matched the actual args.  The
            # `self.expanded_formal_sig` has an attribute `original_formal_sig`
            # which is the original, unexpanded formal signature that matched
            # (after expansion) the actual arguments.  After parsing it is set
            # as the token attribute `original_formal_sig`.  This is important
            # because the `eval_fun` and `ast_data` for tokens are saved in
            # dicts keyed by the original signature at the time when they are
            # defined (via `modify_token`).  So we need the resolved original
            # signature to look up the value.  (Note that if overloading on
            # return types is turned off then these dicts are keyed only on the
            # argument portion of the original typesig.)
            self.original_formal_sig = "Unresolved" # The matching orig sig.
            self.expanded_formal_sig = "Unresolved" # Expanded version of above.
            self.actual_sig = "Unresolved" # The actual signature.

        @classmethod
        def prec(cls):
            """Return the precedence for the token.  This is currently a static
            value for each type of token.  Later it may be dynamic value
            associated with the particular tail function which is selected in a
            given context. Update: may become an attribute of a construct and
            no longer of a token."""
            return cls.static_prec

        def process_not_in_tree(self):
            """Removes any immediate children which have `not_in_tree` set."""
            modified_children = []
            for child in self.children:
                if not hasattr(child, "not_in_tree"):
                    modified_children.append(child)
                else:
                    modified_children += child.children
            self.children = modified_children

        def process_and_check_node(self, construct,
                                   val_type_override=None, all_vals_override=None,
                                   typesig_override=None):
            """This routine is automatically called just after a handler
            function returns a subtree.  It is called for the root of the
            returned subtree.  It sets some attributes and checks that the
            actual types match some defined type signature for the function.

            If `val_type_override` is set to a `TypeObject` instance then the
            return type of both the `expanded_formal_sig` and the `actual_sig`
            for the node is set to that type *after* the first pass of
            processing and type-checking for the subtree is finished.  (This
            option does not currently work for two-pass checking when
            overloading on return types is used.)  This option is useful for
            handling things like parentheses and brackets which inherit the
            type of their child (assuming the parens and brackets are kept as
            nodes in the parse tree and not eliminated).  The override value is
            used for type-checking farther up the expression tree.

            If `all_vals_override` is set to a `TypeObject` instance then all
            the possible signatures have their `val_type` changed to that type
            *before* any checking is done.  This should work for both one and
            two-pass checking, but no check is made for producing duplicate
            types due to the `val_type` changes.

            The `typesig_override` argument must be a `TypeSig` instance.  If
            set it will be *assigned* to the node as its only possible
            `expanded_formal_sig` before type checking (instead of looking up
            the registered ones).  Type checking then proceeds as usual."""

            # Get all the sigs registered for the node's construct.
            if typesig_override is not None:
                all_possible_sigs = [typesig_override]
            else:
                all_possible_sigs = construct.original_sigs
            if all_vals_override:
                all_possible_sigs = [TypeSig(all_vals_override, s.arg_types)
                                                      for s in all_possible_sigs]
            self.all_possible_sigs = all_possible_sigs # Temporary attribute.

            # Do the actual checking.
            if not self.parser_instance.overload_on_ret_types: # One-pass.
                self._check_types_one_pass()
            else: # Two-pass.
                self._check_types_first_of_two_passes()
                # If we have a *unique* matching sig, run pass two on the
                # subtree.  In this case, since the signature is fixed by
                # argument types (regardless of where the top-down pass
                # starts from) we can in this case resolve the types in the
                # subtree early.  Note `check_types_in_tree_second_pass` is
                # also called on the root node from the `parse` method.
                if len(self.matching_sigs) == 1: # matching_sigs set by _check_types
                    self.check_types_in_tree_second_pass()

            # Implement val_type override if set.
            if val_type_override:
                # Note that the original_formal_sig attribute was already set.
                # The ast_data and eval_fun are keyed on that.
                self.expanded_formal_sig = TypeSig(val_type_override,
                                                   self.expanded_formal_sig.arg_types)
                self.actual_sig = TypeSig(val_type_override, self.actual_sig.arg_types)

        def _check_types_one_pass(self):
            """Utility function called from `process_and_check_node` to check
            the actual types against their signatures when overloading is only on
            argument types."""
            all_possible_sigs = self.all_possible_sigs

            # One-pass, each child c has a unique c.expanded_formal_sig already set.
            list_of_child_sig_lists = [[c.expanded_formal_sig] for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)
            # Below all_possible_sigs is saved ONLY for printing error messages.
            self.all_possible_sigs = all_possible_sigs

            # No overloading on return types so we can finalize the actual types.
            if len(self.matching_sigs) != 1:
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution: The actual argument types match"
                        " multiple signatures.")

            # Found a unique signature; set the node's expanded_formal_sig attribute.
            # Saved sig used for eval_fun resolution, ast_data, semantic action, etc.
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type,
                                      [c.actual_sig.val_type for c in self.children])

            # Delete some temporary attributes no longer needed.
            delattr(self, "matching_sigs")
            delattr(self, "all_possible_sigs")

        def _check_types_first_of_two_passes(self):
            """Utility function called from `process_and_check_node` to do the
            first pass in checking the actual types against their signatures.
            Two-pass checking is needed for overloading on return types.  First
            pass goes up the tree, second pass goes back down."""
            all_possible_sigs = self.all_possible_sigs

            # First pass case, multiple sigs in child's self.matching_sigs list.
            list_of_child_sig_lists = [c.matching_sigs for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)

        def check_types_in_tree_second_pass(self, root=False):
            """Recursively run the second pass on the token subtree with the
            `self` node as the root.

            This method currently still needs to be explicitly called for the
            root of the final parse tree, from the `PrattParser` method
            `parse`, as well as from the checking routines here to do partial
            checks on subtrees which are already resolvable."""
            unresolved_children = [
                    c for c in self.children if hasattr(c, "matching_sigs")]
            self._check_types_pass_two() # Call first on self to do top-down.
            for child in unresolved_children: # Recurse on unprocessed children.
                child.check_types_in_tree_second_pass()
            # Delete childrens' matching_sigs lists after they are no longer needed.
            # This also acts as an indicator that the node has been resolved.
            for child in unresolved_children:
                delattr(child, "matching_sigs")
            if root:
                # The final pass in _check_types that deletes these attrs doesn't get
                # run on root, so it is explicitly done here when `root` flag is true.
                delattr(self, "matching_sigs")
                delattr(self, "all_possible_sigs")

        def _check_types_pass_two(self):
            """A second pass is only used when overloading on return types is
            allowed.  It is a top-down pass where each node chooses a unique
            final signature for each of its children.  It depends on the
            node attribute `self.matching_sigs` having been set in the first
            pass."""
            # On FIRST pass: on the way *up* the tree (after getting the
            # literal tokens, the leaves of the tree) get all the signature
            # types for a node which match in arguments for *some* possible
            # return-type choice of the children.  Same as the one-pass
            # version, but now sets of possibilities are allowed and state is
            # saved for the second pass to use: the list of matching sigs is
            # temporarily saved with the node in the self.matched_sigs
            # attribute.
            #
            # Summary: first pass, bottom-up, find all sigs that match possible
            # val_types of the node's children, across all arguments.
            #
            # After the first pass the root should have a unique sig; if not
            # there is ambiguity.  (Each node saved a set of sigs that is
            # satisfiable by some realizable choice of child sigs, and parents
            # can force children to assume any of their possible types).
            #
            # On SECOND pass: On the way *down* the tree, parents choose one
            # sig as final for each child and set it in that child's node as
            # the new self.matching_sigs.  This should always be a unique sig;
            # otherwise there is ambibuity.  Recursively called on children.
            #
            # Summary: second pass, top-down, root is unique and parents assign
            # and set the (unique) signature for each of their children.
            #
            # Note that this algorithm works just as well if the second pass is
            # run on each subtree as soon as the subtree root has a unique
            # signature, and the recursion only goes down to subtrees with
            # roots having a unique signature.  This yields partial results and
            # some error conditions sooner, and is what is implemented here.

            if len(self.matching_sigs) != 1: # The root case needs this.
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution (second pass).  Possible type "
                        "assignments for the children/arguments of the token node match"
                        " {0} possible node signatures: {1}.  Uniqueness is required."
                        .format(len(self.matching_sigs), self.matching_sigs))

            # We have a unique signature; set the node's type attributes
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            # Start setting the actual signature; children will fill arg types
            # when resolved.
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type, [])

            # Set the actual_sig arg_type for the parent (appending in sequence with others).
            if self.parent is not None:
                parent_args_so_far = list(self.parent.actual_sig.arg_types)
                parent_args_so_far.append(self.expanded_formal_sig.val_type)
                self.parent.actual_sig = TypeSig(self.parent.actual_sig.val_type,
                                                 parent_args_so_far)

            # Update the matching_sigs attribute for each child (should be singleton).
            for count, child in enumerate(self.children):
                if not hasattr(child, "matching_sigs"):
                    continue # Already resolved.
                matched_sigs = TypeSig.get_child_sigs_matching_return_arg_type(
                                      child, self.expanded_formal_sig.arg_types[count],
                                      child.matching_sigs)
                # From the first pass, we know at least one child sig matches.
                assert len(matched_sigs) != 0 # Debug.
                if len(matched_sigs) > 1:
                    # Recursion could catch this on the next step, but better err msg.
                    child._raise_type_mismatch_error(matched_sigs,
                        "Token node has multiple signatures with return type matching "
                        "type of parent (pass two). Parent expects type '{0}'.  Defined"
                        " signatures are: {1}."
                        .format(self.expanded_formal_sig.val_type, child.matching_sigs))
                child.matching_sigs = matched_sigs
            return

        def _raise_type_mismatch_error(self, matching_sigs, basic_msg):
            """Raise an error, printing a helpful diagnostic message.  Assumes
            that `_check_types` has been called (to set `self.all_possible_sigs`)."""
            # TODO: Will the self.expanded_formal_sig *ever* be resolved when this routine is
            # called?  If not, then it is not very useful and message could be reworded.
            diagnostic = ("  The current token has value '{0}' and label '{1}'.  "
                         " Its expanded formal signature is {2}.  The"
                         " children/arguments have token labels and values of {3} and "
                         "value types {4}.  The list of matching signatures "
                         "is {5}.  The list of possible signatures was {6}"
                         .format(self.value, self.token_label,
                             self.expanded_formal_sig,
                             list(c.summary_repr() for c in self.children),
                             # Note this below can be "Unresolved", better message?
                             list(c.expanded_formal_sig.val_type
                                  if not isinstance(c.expanded_formal_sig, str)
                                  else c.expanded_formal_sig for c in self.children),
                             matching_sigs, self.all_possible_sigs))
            raise TypeErrorInParsedLanguage(basic_msg + diagnostic)

        #
        # Evaluations and semantic actions.
        #

        @property
        def eval_fun(self):
            """Return the evaluation function saved with the winning construct
            dispatched for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_eval_fun(orig_sig, token_value_key=self.value)

        @property
        def ast_data(self):
            """Return the ast data saved with the winning construct dispatched
            for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_ast_data(orig_sig, token_value_key=self.value)

        def eval_subtree(self):
            """Run the saved evaluation function on the token, if one was
            registered with it.  Returns `None` if no evaluation function is found."""
            orig_sig = self.original_formal_sig # Set during parsing.
            eval_fun = self.eval_fun # Property method above.

            # TODO: Consider if returning None is better than raising exception...
            if not eval_fun:
                return None

            # TODO: Consider if special exception should be raised.
            #if not eval_fun:
            #    raise ParserException("An evaluation function is needed for token with "
            #            "value '{0}' and label '{1}' but no defined and matching "
            #            "evaluation function was found in the dict of eval functions.  "
            #            "The resolved original signature is {2} and the resolve expanded"
            #            " signature is {3}.  The resolved construct_label is {4}.  The "
            #            "token's eval_fun_dict is:\n   {5}."
            #            .format(self.value, self.token_label, orig_sig, sig,
            #                    self.construct_label, self.eval_fun_dict))

            return eval_fun(self)

        #
        # The main recursive_parse function.
        #

        def get_jop_token_instance(self, lex, processed_left, extra_data, subexp_prec):
            """Returns an instance of the jop token iff one should be inferred in the
            current context; otherwise returns `None`."""
            # TODO: extra_data arg now holds subexp_prec as field.
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler

            # Not if jop token is undefined for the parser.
            if not parser_instance.jop_token_subclass:
                return None

            # Not if at end of expression.
            if lex.peek().is_end_token():
                return None

            # Not if the ignored token for jop is set but not present.
            if parser_instance.jop_ignored_token_label and (
                          parser_instance.jop_ignored_token_label
                          not in lex.peek().ignored_before_labels()):
                return None

            # Now infer a jop, but only if 1) its prec would satisfy the while loop
            # in `recursive_parse` as an ordinary token, 2) the next token has
            # a head handler defined in the conditions when the jop will need
            # to run its head handler, and 3) the next token similarly has no
            # tail handler in the context.
            if parser_instance.jop_token_subclass.prec() > subexp_prec:
                # Provisionally infer a jop; create a subclass instance for its token.
                #
                # Todo: Maybe for jop and null-string tokens define methods
                # get_jop_token_instance() which gets the token but calls the
                # lexer to dress it up more like a "real" token, with ignored_before
                # and line numbers, etc. (without putting it in the buffer, of course).
                jop_instance = parser_instance.jop_token_subclass(None)
                jop_instance.extra_data = extra_data

                # This is a little inefficient (since it uses a `go_back` call)
                # but we need to be sure that when the tail handler of the jop
                # is called and it reads a token that that token has a head
                # handler defined for it *in that precondition context*.
                # Otherwise, no jop will be inferred.  We also make sure that
                # it has no tail handler in the context, since then it would be
                # a lower-precedence (lower precedence because we broke out of
                # the loop above) infix or postfix operator, and no jop is
                # inferred before another operator).
                curr_token = lex.next()
                try:
                    # Dispatch here WITHOUT CALLING, since calling will consume
                    # another token; also, deeper-level recursions could cause false
                    # results to come up the recursion chain.  We are just testing
                    # what handlers are defined for the token.
                    _peek_head_handler, head_construct = dispatch_handler(
                                                   HEAD, curr_token, lex, extra_data)
                    try: # Found head handler, now make sure it has no tail handler.
                        _peek_tail_handler, tail_construct = dispatch_handler(
                                   TAIL, curr_token, lex, extra_data, processed_left)
                    except NoHandlerFunctionDefined:
                        # This is the only case where an actual token is returned.
                        return jop_instance
                    else:
                        return None
                except NoHandlerFunctionDefined:
                    return None # No precondition matches, assume no jop.
                finally:
                    #delattr(curr_token, "extra_data") # Only needed if pushback below, not go_back.
                    lex.go_back(1)
            else:
                return None

        def dispatch_null_string_handler(self, head_or_tail, lex, subexp_prec,
                                         extra_data, processed_left=None):
            """Check for any possible matching null-string token handlers;
            return the token and the matching handler if one is found.

            Note that the precedence for a null-string token is set to
            `subexpr_prec`, so it would always have activated the while loop if
            it were a real token."""
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            # See if a null-string token is set and a handler matches preconds.
            if not parser_instance.null_string_token_label:
                return None, None, None
            else:
                # TODO: Later don't re-create each time, save one.
                null_string_token = parser_instance.null_string_token_subclass(None)
            null_string_token.extra_data = extra_data

            curr_token = None
            handler_fun = None
            construct = None
            try:
                handler_fun, construct = dispatch_handler(head_or_tail,
                                                          null_string_token,
                                                          lex, extra_data, processed_left)
                curr_token = null_string_token
            except NoHandlerFunctionDefined:
                pass
            return curr_token, handler_fun, construct

        def recursive_parse(self, subexp_prec, only_head=False):
            """Parse a subexpression as defined by token precedences. Return
            the result of the evaluation.  Recursively builds up the final
            result in `processed_left`, which is the tree for the part of the
            full expression to the left of the current token.

            The list `lookbehind` saves all the previously evaluated
            subexpressions at this level of recursion (i.e., at the top level
            in the same subexpression) and passes it to the dispatched tail
            handlers, in case that routine wants to make use of it.  For
            example, the ordinal position of the token in the top level of the
            subexpression can be calculated from the length of `lookbehind`.

            This function is made a method of `TokenSubclass` so that handler
            functions can easily call it by using `tok.recursive_parse`, and
            also so that it can access the lexer without it needing to be
            passed as an argument.  It is basically a static function,
            though.

            The `extra_data` attribute is set for all triggering tokens, and is
            guaranteed to be available for precondition functions and for
            handler functions.  It is set before any dispatches or recursive calls,
            and is deleted from the token after the recursive call.  It is an
            advanced feature which most users will not need."""
            # Note that all the dispatching functions set the `extra_data`
            # attribute of their token before the dispatching is done, but they
            # do not update `extra_data` itself in any way.

            # Note on below code: It is tempting for efficiency to define a jop
            # and null-string token instance, save it, and only use it when
            # necessary (replacing it only when used).  But some things need to
            # be considered.
            #
            # Now that handlers are not with tokens, that is no longer a
            # concern... TODO go ahead and do this.
            #
            # Is there any special attribute or other thing that is assigned on
            # creation which might change?  Either way, you should probably add
            # extra things like line numbers to mimic ordinary tokens. Note
            # that currently you only really pay the creation cost if you
            # actually use the jop or null-string feature, but a lot of dummy
            # instances are created if you do.

            # This err check catches some cases of tokens defined via Lexer, not all.
            if not hasattr(self, "token_kind"):
                raise ParserException("All tokens used in the parser must be"
                        " defined in via parser's methods, not the lexer's.")

            #
            # Initialize, and set some shorter aliases.
            #

            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            lex = self.token_table.lex
            extra_data = ExtraDataTuple(lookbehind=[], constructs=[],
                                        subexp_prec=subexp_prec)

            #
            # Start the actual Pratt parsing recursion.
            #

            curr_token, head_handler, construct = self.dispatch_null_string_handler(
                                                     HEAD, lex, subexp_prec, extra_data)
            if not curr_token: # No null-string token fired, so use normal next() call.
                curr_token = lex.next()
                head_handler, construct = dispatch_handler(
                                                     HEAD, curr_token, lex, extra_data)

            extra_data.constructs.append(construct)

            # TODO: Should the root of processed_left be set for is_head instead, for
            # general case?  Or set "head_trigger_token" to label instead of None?
            # Consider how lookup will work in usual and general cases of arbitrary
            # token as subtree root.
            curr_token.is_head = True # Used to look up eval_fun and ast_data later.

            processed_left = head_handler()

            delattr(curr_token, "extra_data") # Delete after recurse, allow mem cleanup.
            extra_data.lookbehind.append(processed_left)
            extra_data.constructs.append(construct)

            if only_head:
                return processed_left

            while True:

                #
                # The loop below is the main loop in ordinary Pratt parsing.  The
                # Outer loop is ONLY for the special case when a jop is defined.
                #

                # TODO: Consider modification like code below to allow
                # precedences per constuct, which also makes "prec - 1" no
                # longer necessary for right assoc when property is set for the
                # construct itself.  See what performance hit it has, one
                # go_back per subexpression.  Note that jops use a single
                # go_back already when they are defined...
                #
                # The ugly comment-string code below works.  It just pulls the
                # token-dispatching out to before the precedence test.
                # Obviously could then use some cleanup and refactoring, too.
                # Consider possible interactions with jop and null-string
                # tokens, but they don't do a `next` call anyway.  (Is it
                # better to pull out the ns_token dispatch, at least?  In
                # regular code, how to get null-string to appear at end of a
                # subexpression?)
                #
                # Argument it works: This code is doing exactly the same
                # dispatching as it would inside the loop test, but it is doing
                # it before the loop test.  The loop test never modifies
                # anything.  If the test fails the effects of the dispatches
                # are undone.
                """
                while True:
                    #err = None
                    ns_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if ns_token:
                        curr_token = ns_token
                        peek_prec = lex.token.prec()
                        #peek_prec = construct.prec() # Switch to this...
                    else:
                        curr_token = lex.next()
                        try:
                            tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                            lex, extra_data, processed_left)
                            peek_prec = lex.token.prec()
                            #peek_prec = construct.prec() # Switch to this...
                        except NoHandlerFunctionDefined as e:
                            # If no construct at all then can't have tail handler so
                            # prec should be 0.  But if it fails due to a precond,
                            # token itself could still have a prec > 0.  In that case
                            # it will get inside the loop and fail, but it really
                            # shouldn't have gotten inside.
                            #
                            # Only one test changes, and new one is commented out in
                            # the test file under the old one.
                            #err = e
                            peek_prec = -1 # Always fail test and break.
                            #peek_prec = lex.token.prec()

                    #test_assoc = False if err else (peek_prec == subexp_prec and
                    #                                construct.assoc == "right")
                    test_assoc = peek_prec == subexp_prec and construct.assoc == "right"
                    if peek_prec > subexp_prec or test_assoc:
                        #if err: # Error would have been found inside loop, now above.
                        #    raise err # Avoid error msg changing (makes test fail).
                        processed_left = tail_handler()
                        delattr(curr_token, "extra_data")
                        extra_data.lookbehind.append(processed_left)
                        extra_data.constructs.append(construct)
                    else:
                        if not ns_token:
                            lex.go_back(1)
                        break
                """

                while lex.peek().prec() > subexp_prec:

                    curr_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if not curr_token: # No null handler fired off, get regular way.
                        curr_token = lex.next()
                        tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                        lex, extra_data, processed_left)

                    processed_left = tail_handler()
                    delattr(curr_token, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)

                #
                # Broke out of main loop, determine whether or not to infer a jop.
                #

                jop_instance = self.get_jop_token_instance(
                                         lex, processed_left, extra_data, subexp_prec)
                if jop_instance:
                    jop_tail_handler, construct = dispatch_handler(TAIL, jop_instance,
                                                        lex, extra_data, processed_left)
                    processed_left = jop_tail_handler()
                    delattr(jop_instance, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)
                else:
                    break

            return processed_left

        #
        # Copying instances of tokens.
        #

        def __copy__(self):
            """Return a shallow copy of the token."""
            return copy.copy(self)

        #
        # Some representations that apply to the subclasses.
        #

        def summary_repr_with_types(self):
            """A short summary repr of the node, without its children."""
            return ("<" + str(self.token_label) +
                    ",'" + str(self.value) +
                    "'," + str(self.expanded_formal_sig.val_type) + ">")

        def tree_repr_with_types(self, indent=""):
            """Token representation as the root of a parse subtree, with formatting.
            The optional `indent` parameter can be either an indent string or else
            an integer for the number of spaces to indent.  Note that the ordinary
            `tree_repr` method without types is also available, inherited from
            the base node object."""
            try:
                num_indent = int(indent)
            except ValueError:
                pass
            else:
                indent = " " * num_indent
            string = indent + self.summary_repr_with_types() + "\n"
            for c in self.children:
                string += c.tree_repr_with_types(indent=indent+" "*4)
            return string

        def string_repr_with_types(self):
            """A string repr for the tree that includes type information."""
            string = self.summary_repr_with_types()
            if self.children:
                string += "("
                string += ",".join(c.string_repr_with_types() for c in self.children)
                string += ")"
            return string

        @classmethod
        def class_repr(cls):
            """Print out the `TokenSubclass` classes (representing tokens) in a
            nice way.  The default is hard to read."""
            string = "Token({0})".format(cls.token_label)
            return string

    return TokenSubclass # Return from token_subclass_factory function.

#
# Parser
#

def lexer_add_parser_instance_attribute(lexer, token):
    """Passed to lexer to add a `parser_instance` attribute to each token it
    returns.  This attribute is added to instances at the lexer, from its
    current token table, because of the case where parsers call other parsers.
    (It is not added to general token subclasses in `def_token_master` because
    parsers could potentially share token subclasses.)"""
    token.parser_instance = lexer.token_table.parser_instance # From token table.
    return token

# Could also add parser_instance and construct as fields of the extra data tuple.
# Could extra_data also be passed to handler functions?  Nice to have construct
# instance available there, perhaps.  TODO: Consider.
ExtraDataTuple = namedtuple("ExtraHandlerData", ["lookbehind",
                                                 "constructs",
                                                 "subexp_prec"])

class PrattParser(object):
    """A parser object.  Each parser object contains a table of defined tokens,
    a lexer, a table of constructs, and a table of defined types."""
    def __init__(self, max_peek_tokens=None,
                       max_deque_size=None,
                       lexer = None,
                       default_begin_end_tokens=True,
                       type_table = None,
                       skip_type_checking=False,
                       overload_on_arg_types=True,
                       overload_on_ret_types=False,
                       partial_expressions=False,
                       parser_label=None,
                       raise_on_equal_priority_preconds=False):
        """Initialize the parser.

        The `max_peek_tokens` parameter is an optional arbitrary limit on the
        level of peeks allowed in the lexer.  Setting to 1 limits it to a
        single token lookahead.  The default setting `None` gives
        peek-on-demand as far ahead as requested.

        The `max_deque_size` parameter is an optional limit on the size of the
        deque that the lexer keeps for previous tokens, the current token, and
        requested peek tokens.  The default is for it to grow arbitrarily
        (though it is reset on each parse).  Needs to be large enough for the
        max level of peeks required plus the max `go_back` level required.

        If a `Lexer` instance is passed in the parser will use that lexer and
        its token table, otherwise a new lexer is created.  The any other lexer
        options are ignored.

        No default begin and end functions will be set if a lexer is passed in,
        regardless of the value of `default_begin_end_tokens`.  Otherwise,
        default begin and end tokens will be defined unless
        `default_begin_end_tokens` is set false (note that creating them by
        default is the opposite of the default behavior for the lower-level
        Lexer class).

        Setting `skip_type_checking=True` is slightly faster since typing is
        not being used at all.  Note that overloading depends on type-checking
        to resolve the actual types, so this flag implies that the overload
        flags are all false.  The default is false.  It should be possible to
        define types, use them during testing, and then turn checking off ---
        provided overloading is not used to get different evaluation functions
        or AST data elements for different overloads.

        The `overload_on_arg_types` flag specifies whether or not to overload
        on argument types.  The default is true.  Cannot be changed after
        initialization.

        Setting `overload_on_ret_types` also overloads on argument types.  It
        requires an extra walk of the token tree, and implies overloading on
        argument types.  The default is false.  Cannot be changed after
        initialization.

        If `partial_expressions` is set true then no check will be made in the
        `parse` method to see if the parsing consumed up to the end-token in
        the lexer.  Multiple expression text can be parsed by repeatedly
        calling `parse` when this option is true and checking whether the
        lexer's current token is the end-token.

        The `parser_label` is an optional descriptive string for a parser.
        These can be useful in debugging when they appear in error messages,
        especially when working with multiple parser instances.

        If `raise_on_equal_priority_preconds` is true then an exception will be
        raised if two precondition functions are registered with the same
        trigger token in the same head or tail position which have the same
        precondition priority.  The default is false, and the first-defined
        matching precondition function of the same priority will win any
        competition when several are true.  This option can be used to ensure
        at language define-time that there is no definition-order dependence in
        dispatching.  If two such preconditions functions are mutually
        exclusive there is no problem with them having the same priority, but
        this condition cannot be checked by a program.  A small difference can
        be added."""

        if parser_label:
            self.parser_label = parser_label # Set first, for error messages.
        else:
            self.parser_label = None

        ## Type-checking options below; these cannot be changed after initialization.
        if overload_on_ret_types:
            overload_on_arg_types = True # Overload on ret implies overload on args.
        self.skip_type_checking = skip_type_checking # Skip all type checks, faster.
        if not skip_type_checking:
            self.overload_on_arg_types = overload_on_arg_types
            self.overload_on_ret_types = overload_on_ret_types
        else: # Overloading requires type checking.
            self.overload_on_arg_types = False
            self.overload_on_ret_types = False

        # If exceptions are not raised on ties then with non-mutually-exclusive
        # precond functions the first-set one will have precedence when they
        # are both true.  Need to define this before registering any handlers (
        # which is done below in `def_begin_end_tokens`).
        self.raise_on_equal_priority_preconds = raise_on_equal_priority_preconds
        #self.raise_on_equal_priority_preconds = True # DEBUG

        self.construct_table = ConstructTable(parser_instance=self) # Dict of constructs.
        self.default_construct_label_number = 0 # For unique precondition labels.

        if lexer: # Lexer passed in.
            self.lex = lexer
            self.token_table = lexer.token_table
        else: # No Lexer passed in.
            self.token_table = TokenTable(
                                token_subclass_factory_fun=token_subclass_factory)
            self.lex = Lexer(self.token_table,
                             max_peek_tokens=max_peek_tokens,
                             max_deque_size=max_deque_size,
                             default_begin_end_tokens=False)
            # Set the begin and end tokens unless the user specified not to.
            if default_begin_end_tokens:
                self.def_begin_end_tokens() # Use function's defaults.
        self.lex.default_helper_exception = ParserException # Default for match_next, etc.
        # Add mod function to lexer here, works even if they passed in a lexer.
        self.lex.final_mod_function = lexer_add_parser_instance_attribute

        self.token_table.parser_instance = self # Give token table ref to parser.

        if type_table:
            self.type_table = type_table
        else:
            self.type_table = TypeTable(self)

        self.num_lookahead_tokens = max_peek_tokens
        self.jop_token_label = None # Label of the jop token, if any.
        self.jop_token_subclass = None # The actual jop token, if defined.
        self.null_string_token_label = None # Label of the null-string token, if any.
        self.null_string_token_subclass = None # The actual null-string token, if any.

        self.partial_expressions = partial_expressions # Whether to parse multiple expressions.

        self.pstate_stack = [] # Stack of production rules used in grammar parsing.
        self.top_level_production = False # If true, require grammar parses to consume to end.
        self.disable_pstate_processing = False # Set to temporarily disable grammar parsing.

    #
    # Methods defining tokens.
    #

    def def_token_master(self, token_label, regex_string=None, on_ties=0, ignore=False,
                         token_kind="regular", ignored_token_label=None,
                         matcher_options=None):
        """The master method for defining tokens; all the convenience methods
        actually call it.  Allows for factoring out some common code and
        keeping the attributes of all the different kinds of tokens up-to-date.
        This routine calls the underlying lexer's `def_token` to get tokens and
        then adds extra attributes needed by the `PrattParser` class.

        The `token_kind` argument must be one of the following strings:
        `"regular"`, `"ignored"`, `"begin"`, `"end"`, `"jop"`, or
        `"null-string"`.  The `ignored_token_label` is used only when defining
        a jop.

        Tokens can be shared between parsers if all their properties are the
        same.  Note that for now this includes the precedence value for any
        tail handlers (since that is made a token attribute).  Null-string and
        jop tokens are the exception, but they are special in that they are
        never returned by the lexer, only by a particular parser."""
        token_table = self.token_table

        if token_kind == "regular":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=ignore, matcher_options=matcher_options)

        elif token_kind == "ignored":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=True, matcher_options=matcher_options)

        elif token_kind == "begin":
            tok = token_table.def_begin_token(token_label)
            self.begin_token_label = token_label
            # Define dummy handlers for the begin-token, just to catch errors.
            def begin_head(self, lex):
                """Dummy head handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called head-handler for begin token.")
            def begin_tail(self, lex, left):
                """Dummy tail-handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called tail-handler for begin token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, begin_head, token_label)
            self.def_construct(TAIL, begin_tail, token_label, dummy_handler=True)
            self.begin_token_subclass = tok

        elif token_kind == "end":
            tok = token_table.def_end_token(token_label)
            self.end_token_label = token_label
            # Define dummy handlers for the end-token, just to catch errors.
            def end_head(self, lex):
                """Dummy head handler for end-tokens."""
                raise CalledEndTokenHandler("Called head-handler for end token.")
            def end_tail(self, lex, left):
                """Dummy tail-handler for end-tokens."""
                raise CalledEndTokenHandler("Called tail-handler for end token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, end_head, token_label)
            self.def_construct(TAIL, end_tail, token_label, dummy_handler=True)
            self.end_token_subclass = tok

        elif token_kind == "jop":
            if self.jop_token_subclass:
                raise ParserException("A jop token is already defined.  It must be "
                                      "undefined before defining a new one.")
            self.jop_token_label = token_label
            self.jop_ignored_token_label = ignored_token_label
            tok = token_table.def_token(token_label, None)
            self.jop_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        elif token_kind == "null-string":
            if self.null_string_token_subclass:
                raise ParserException("A null-string token is already defined.  It"
                         " must be undefined before defining an new one.")
            self.null_string_token_label = token_label
            tok = token_table.def_token(token_label, None)
            self.null_string_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        else:
            raise ParserException("Bad call to def_token_master, with unrecognized"
                    ' string "{0}" for the keyword argument token_kind.'
                    .format(token_kind))

        tok.token_kind = token_kind
        tok.is_head = False # Set true in recursive_parse if instance parses as a head.
        return tok

    def def_token(self, token_label, regex_string, on_ties=0, ignore=False,
                  matcher_options=None):
        """Define a token.  Use this instead of the Lexer `def_token` method,
        since it adds extra attributes to the tokens."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore,
                              token_kind="regular", matcher_options=matcher_options)

    def def_ignored_token(self, token_label, regex_string, on_ties=0,
                          matcher_options=None):
        """A convenience function to define a token with `ignored=True`."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore=True,
                              token_kind="ignored", matcher_options=matcher_options)

    def def_begin_end_tokens(self, begin_token_label="k_begin",
                                   end_token_label="k_end"):
        """Calls the `Lexer` method to define begin- and end-tokens.  The
        subclasses are then given initial head and tail functions for use in
        the Pratt parser.  To use the `PrattParser` this method must be called,
        not the method of `Lexer` with the same name (since it also creates
        head and tail handler functions that raise exceptions for better error
        messages).  The default is to call this method automatically on
        initialization, with the default token labels for the begin and end
        tokens.  If the flag `default_begin_end_tokens` is set false on
        `PrattParser` initalization then the user must call this function
        (setting whatever token labels are desired).  Returns a tuple
        containing the new begin and end `TokenNode` subclasses."""
        begin_tok = self.def_token_master(begin_token_label, token_kind="begin")
        end_tok = self.def_token_master(end_token_label, token_kind="end")
        return begin_tok, end_tok

    def def_jop_token(self, jop_token_label, ignored_token_label):
        """Define a token for the juxtaposition operator.  This token has no
        regex pattern.  An instance is inserted in `recursive_parse` when it is
        inferred to be present.  This method must be explicitly called before a
        juxtaposition operator can be used (i.e., before `def_jop`).  The
        parameter `jop_token_label` is the label for the newly-created token
        representing the juxtaposition operator.  The `ignored_token_label`
        parameter is the label of an ignored token which must be present for a
        jop to be inferred.  Some already-defined token is required; usually it
        will be a token for spaces and tabs.  If set to `None` then no ignored
        space at all is required (i.e., the operands can be right next to each
        other)."""
        return self.def_token_master(jop_token_label,
                                     ignored_token_label=ignored_token_label,
                                     token_kind="jop")

    def def_null_string_token(self, null_string_token_label="k_null-string"):
        """Define the null-string token.  This token has no regex pattern.  An
        instance is inserted in `recursive_parse` when it is inferred to be
        present based.  This method must be called before a
        null-string can be used.  The parameter `null_string_token_label` is
        the label for the newly-created tok representing it."""
        return self.def_token_master(null_string_token_label,
                                     token_kind="null-string")

    def get_token(self, token_label):
        """Return the token with the label `token_label`.  The reverse
        operation, getting a label from a token instance, can be done by
        looking at the `token_label` attribute of the token."""
        return self.token_table[token_label]

    #
    # Undefine tokens.
    #

    def undef_token(self, token_label):
        """A method for undefining any token defined by the `PrattParser` methods.
        Since the `token_kind` was set for all tokens when they were defined
        it knows how to undelete any kind of token."""
        # TODO: Make sure this is up-to-date with the what the token_master class does.
        token_table = self.token_table
        tok = token_table[token_label]
        kind = tok.token_kind
        if kind == "jop":
            token_table.undef_token(self.jop_token_label)
            self.jop_token_subclass = None
            self.jop_token_label = None
            self.jop_ignored_token_label = None
        elif kind == "null-string":
            token_table.undef_token(self.null_string_token_label)
            self.null_string_token_subclass = None
            self.null_string_token_label = None
            self.null_string_ignored_token_label = None
        else:
            token_table.undef_token(token_label)

    #
    # Methods to define and undefine constructs.
    #

    def def_construct(self, head_or_tail, handler_fun, trigger_token_label,
                      prec=0, construct_label=None, precond_fun=None,
                      precond_priority=0, val_type=None, arg_types=None,
                      eval_fun=None, ast_data=None, token_value_key=None,
                      dummy_handler=False):
        """Define a construct and register it with the token with label
        `trigger_token_label`.  A token with that label must already be in the
        token table or an exception will be raised.

        Stores the construct instance in the parser's construct table and also
        return the construct instance.

        The `head_or_tail` argument should be set to either `HEAD` or `TAIL`.
        If `head_or_tail==TAIL` then the operator precedence will be set to
        `prec`.  For a head handler the `prec` value is ignored and effectively
        set to zero.  For a tail handler a `prec` value greater than zero is
        required or else an exception will be raised (unless `dummy_handler` is
        set true).  Similarly, an exception is raised for a non-zero `prec`
        value for a head-handler (the default value).

        The `construct_label` is an optional string value which can result in
        better error messages.

        The `eval_fun` and the `ast_data` arguments are saved in dicts
        associated with the type signature.

        If `token_value_key` is set to a string value then that value will be
        part of the key tuple for saving AST data and evaluation functions.
        This can be used, for example, when overloading a generic identifier
        with different evaluation functions for when the identifier value is
        `sin`, `cos`, etc.  In looking up the AST data and evaluation function
        the parsed token's actual string value (from the program text) is used
        as the key.  If any overload of a particular construct provides a
        `token_value_key` string then all the other overloads for that
        construct must also (for the time being, at least)."""
        # Note that the parser_instance attribute of tokens is not necessarily
        # set yet when this method is called.
        if isinstance(arg_types, str):
            raise ParserException("The arg_types argument to token_subclass must"
                    " be None or an iterable returning type labels (e.g., a list"
                    " or tuple).")

        if head_or_tail == TAIL and prec <= 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a tail hander and a precedence of zero or less."
                    .format(trigger_token_label))
        if head_or_tail == HEAD and prec != 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a head hander and a precedence not equal to zero."
                    .format(trigger_token_label))

        if precond_fun is None:
            precond_fun = DEFAULT_ALWAYS_TRUE_PRECOND_FUN

        if trigger_token_label in self.token_table:
            trigger_token_subclass = self.get_token(trigger_token_label)
        else:
            raise ParserException("In call to def_construct: subclass for"
                    " token labeled '{0}' has not been defined.  Maybe try"
                    " calling def_token first.".format(trigger_token_label))
            # Below line formerly just created a subclass, but that can mask errors!
            #TokenSubclass = self.token_table.create_token_subclass(token_label)

        if not hasattr(trigger_token_subclass, "token_kind"):
            raise ParserException("Token with label '{0}'  must be defined by the"
                                  " parser's def_token method, not the lexer's method."
                                  .format(trigger_token_label))

        # TODO: Precedence is currently saved as a token attribute.  Consider
        # saving it in the construct instead.  See main Sphinx docs, unimplemented
        # generalizations.
        if head_or_tail == TAIL:
            if (trigger_token_subclass.static_prec != 0 and
                    prec != trigger_token_subclass.static_prec):
                raise ParserException("Redefining the precedence of the triggering"
                        " token subclass '{0}' to a new value {1} not equal"
                        " to the previous nonzero value of {2}."
                        " The original precedence will never be used.  To actually"
                        " reset the value, set trigger_token_label.static_prec=0"
                        " explicitly before this call to def_construct.  Currently"
                        " all operators with the same triggering token must have"
                        " the same precedence value, regardless of preconditions."
                        .format(trigger_token_label, prec,
                                trigger_token_subclass.static_prec))
            trigger_token_subclass.static_prec = prec # Ignore prec for heads; will stay 0.

        # Create the type sig object.
        if self.skip_type_checking:
            type_sig = None
        else:
            type_sig = TypeSig(val_type, arg_types)

        # Register the handler funs.
        construct = self.construct_table.register_construct(
                                          head_or_tail=head_or_tail,
                                          trigger_token_subclass=trigger_token_subclass,
                                          handler_fun=handler_fun,
                                          precond_fun=precond_fun,
                                          precond_priority=precond_priority,
                                          construct_label=construct_label,
                                          type_sig=type_sig,
                                          eval_fun=eval_fun,
                                          ast_data=ast_data,
                                          token_value_key=token_value_key)
        return construct

    def undef_construct(self, construct, type_sig=None, token_value_key=None):
        """Undefine a construct.  If `type_sig` is passed a `TypeSig` instance then
        only that overload is deleted.  If `token_value_key` is also defined then
        only that token key is unregistered.  Otherwise the full construct is
        removed from the parser's construct table."""
        # Note users themselves could unregister the overloads if they have the
        # construct instance.
        self.construct_table.unregister_construct(construct, type_sig, token_value_key)

    #
    # Methods dealing with types.
    #

    def def_type(self, type_label):
        """Define a type associated with the name `type_label`."""
        return self.type_table.create_typeobject(type_label)

    def undef_type(self, type_label):
        """Undefine the type associated with the name `type_label`."""
        self.type_table.undef_typeobject(type_label)

    #
    # The main parse routines.
    #

    def parse_from_lexer(self, lexer_to_use, pstate=None):
        """The same as the `parse` method, but a lexer_to_use is already assumed to be
        initialized.  This is ONLY used when one parser instance calls another
        parser instance (implicitly, via the handler functions of its tokens).
        The outer parser calls this routine of the inner, subexpression parser.
        Such a call to another parser would look something like::

            alternate_parser.parse_from_lexer(lexer_to_use)

        where `lexer_to_use` is the lexer_to_use of the outer parser.  This routine
        temporarily swaps the token table for the passed-in lexer_to_use to be the
        token table for this parser (remember that this parser is the inner
        parser when this routine is called)."""
        # Note you do not need to set the type_table, since the tokens always
        # have fixed references to their own parser instance.

        # Set up to read from lexer_to_use, after setting its token table to
        # be the token table for this parser (this is the inner parser).

        # Temporarily change new lexer's token table.
        lexer_to_use_usual_table = lexer_to_use.token_table
        lexer_to_use.set_token_table(self.token_table)

        # Swap the lexer in.
        usual_lexer = self.lex
        self.lex = lexer_to_use # Swap the lexer.

        try:
            parsed_subexpression = self.parse("IGNORED", pstate=pstate,
                                    partial_expressions=True,
                                    skip_lex_setup=True)
        except ParserException:
            print("Error in `parse_from_lexer` method, in call to `parse` method"
                    " using a different parser's lexer for a subexpression.",
                    file=sys.stderr)
            raise
        finally:
            # Restore the temporary lexer's token table.
            lexer_to_use.set_token_table(lexer_to_use_usual_table)
            self.lex = usual_lexer
        return parsed_subexpression

    def parse(self, program, pstate=None, partial_expressions=None,
                                                      skip_lex_setup=False):
        """The main routine for parsing a full program or expression.  Users of
        the class should call this method to perform the parsing operations
        (after defining a grammar, of course).

        Unless there was a parsing failure or `partial_expressions` is true
        then the lexer is left with the end-token as the current token.

        If the `pstate` variable is set then the value will be pushed as the
        initial state on the production rule stack `pstate_stack`.  The stack
        is then cleared after a successful call.  (Set the parser attribute
        directly for more control.)

        The parser's `partial_expressions` attribute will be used unless it is
        overridden by the parameter `partial_expressions` here.  When it is
        true no check is made for the end-token after `recursive_parse` returns
        a value.    The lexer will be left at the last token consumed, so a
        check for the end-token will tell when all the text was consumed.
        Users are responsible for making sure their grammars are suitable for
        this kind of parsing if the option is set.

        If the `skip_lex_setup` parameter is true then the text `program` is
        ignored and lexer setup is skipped.  This is generally ONLY used when
        multiple parsers are parsing from a common text stream, and `parse` is
        called from the method `parse_from_lexer`."""
        if pstate:
            self.pstate_stack = [pstate] # For parsing production rule grammars.
        if partial_expressions is None:
            partial_expressions = self.partial_expressions

        if not skip_lex_setup:
            self.lex.set_text(program)
        begin_tok = self.lex.token # Get the first token to access recursive_parse.
        parse_tree = begin_tok.recursive_parse(0)

        # Finalize type-checking for root when overloading on return types.
        if self.overload_on_ret_types:
            parse_tree.check_types_in_tree_second_pass(root=True)

        # See if we reached the end of the token stream.
        if not self.lex.peek().is_end_token() and not partial_expressions:
            raise IncompleteParseException("Parsing never reached the end of"
                " the text.  Parsing stopped with tokens still in the lexer."
                "  No syntax element was recognized. The last-parsed token had"
                " value '{0}' and label '{1}'.  Parsing stopped before a token"
                " in the lexer with value '{2}' and label '{3}'.  The partial"
                " result returned is:\n{4}"
                .format(self.lex.token.value, self.lex.token.token_label,
                        self.lex.peek().value, self.lex.peek().token_label,
                        parse_tree.tree_repr()))

        if pstate:
            self.pstate_stack = []
        return parse_tree

#
# Copy the convenience functions from builtin_parse_methods to the PrattParser class.
#

for method in builtin_parse_methods.parse_methods:
    setattr(PrattParser, method.__name__, method)

for method in predefined_token_sets.token_defining_methods:
    setattr(PrattParser, method.__name__, method)

#
# Exceptions
#

class IncompleteParseException(ParserException):
    """Only raised at the end of the `PrattParser` function `parse` if tokens
    remain in the lexer after the parser finishes its parsing."""
    pass

class TokenSubclassMeta(type):
    """A trivial metaclass that will actually create the `TokenSubclass`
    objects.  Since tokens are represented by classes, rather than instances,
    this is necessary in order to change their `__repr__` (the defalt one is
    ugly for tokens) and to overload operators to work for token operands
    in the EBNF-like grammar."""
    def __new__(mcs, name, bases, dct):
        new_class = super(TokenSubclassMeta, mcs).__new__(mcs, name, bases, dct)

        # Below is ugly, but avoids mutual import problems.  Used as an easy
        # way to define token addition so that it works in the grammars defined
        # by the ebnf_classes_and_operators module.
        from .ebnf_classes_and_operators import (
                                     Tok, Not, Prec, nExactly, nOrMore, Repeat)
        # These are saved in a dict below because if they are made attributes
        # then Python 2 complains about "TypeError: unbound method Tok() must
        # be called with TokenClass_k_lpar instance as first argument (got
        # TokenSubclassMeta instance instead)".
        new_class.prod_rule_funs = {
                "Tok": Tok,
                "Not": Not,
                "Prec": Prec,
                "nExactly": nExactly,
                "nOrMore": nOrMore,
                "Repeat": Repeat,
                }
        return new_class

    #
    # Define a nicer-looking __repr__, since the classes represent tokens.
    #

    def __repr__(cls):
        """The representation for tokens.  Tokens are commonly used in the
        code but, being classes, have an ugly default `__repr__` when printed out.
        In this metaclass we can define a better `__repr__` for tokens."""
        string = "TokenClass_{0}".format(cls.token_label)
        return string

    #
    # These overloads work with the ebnf_classes_and_operators module.
    #

    # TODO: Could have a flag to turn overloads on and off, maybe.
    # Might want to turn off when not processing a grammar expression
    # using the tokens, but it really shouldn't matter much.
    def __add__(cls, other):
        """Addition of two tokens is defined to simply return a tuple of
        both tokens.  This is so raw tokens can be used in the operator
        overloaded form of defining production rules for a grammar."""
        return cls.prod_rule_funs["Tok"](cls) + other

    def __radd__(cls, left_other):
        """The right version of `__add__` above."""
        return left_other + cls.prod_rule_funs["Tok"](cls)

    def __or__(cls, other):
        """The `|` symbol simply converts this object into an `ItemList`
        and then calls `__or__` for those objects."""
        return cls.prod_rule_funs["Tok"](cls) | other

    def __ror__(cls, left_other):
        """The right version of `__or__` above."""
        return left_other | cls.prod_rule_funs["Tok"](cls)

    def __rmul__(cls, left_other):
        """The expression `n*token` for an int `n` is "n occurrences of"
        `token`."""
        return cls.prod_rule_funs["Repeat"](left_other, cls)

    def __rpow__(cls, left_other):
        """The expression `n**token` for an int `n` is "n or more occurrences of"
        `token`."""
        return cls.prod_rule_funs["nOrMore"](left_other, cls)

    def __invert__(cls):
        """Define the `~` operator for production rule grammars."""
        return cls.prod_rule_funs["Not"](cls)

    def __getitem__(cls, arg):
        """Define the bracket indexing operator for production rule grammars
        to set the precedence."""
        return cls.prod_rule_funs["Prec"](cls, arg)

def token_subclass_factory():
    """This function is called from the `create_token_subclass` method of
    `TokenTable` when it needs to create a new subclass to begin
    with.  It should not be called directly.

    Create and return a new token subclass which will be modified and used
    to represent a particular kind of token.  Specifically, each scanned token
    matching the regex defined for tokens with a given token label is
    represented as an instance of the subclass created by calling this function
    (with further attributes, such as the token label, added to it).

    Using a separate subclass for each token label allows for attributes
    specific to a kind of token (including head and tail handler methods) to
    later be added to the class itself without conflicts.  This function
    returns a bare-bones subclass without any head or tail functions, etc."""

    class TokenSubclass(TokenSubclassMeta("TokenSubclass", (object,), {}), TokenNode):
    #class TokenSubclass(TokenNode, metaclass=TokenSubclassMeta):  # Python 3
    #class TokenSubclass(TokenNode):                               # No metaclass.
        """The factory function returns this class to represent tokens.  It is a
        subclass of the `TokenNode` class, defined in the lexer module."""
        static_prec = 0 # The prec value for this kind of token, with default zero.
        token_label = None # Set to the actual value later, by create_token_subclass.
        #parser_instance = None # Set by recursive_parse. AVOID if not needed.

        def __init__(self, value):
            """Initialize an instance of the subclass for a token of the kind
            labeled with `token_label`.  The `value` is the actual parsed
            string from the text.  This instance represents the token."""
            super(TokenSubclass, self).__init__() # Call base class __init__.
            self.value = value # Set from lex.token_generator; static value=None.

            # The `expanded_formal_sig` attr is set upon parsing.  It is the
            # expanded form of one of the formal sigs which were registered
            # with the token (the expansion handles wildcards, repeat options,
            # etc.)  It is the signature which matched the actual args.  The
            # `self.expanded_formal_sig` has an attribute `original_formal_sig`
            # which is the original, unexpanded formal signature that matched
            # (after expansion) the actual arguments.  After parsing it is set
            # as the token attribute `original_formal_sig`.  This is important
            # because the `eval_fun` and `ast_data` for tokens are saved in
            # dicts keyed by the original signature at the time when they are
            # defined (via `modify_token`).  So we need the resolved original
            # signature to look up the value.  (Note that if overloading on
            # return types is turned off then these dicts are keyed only on the
            # argument portion of the original typesig.)
            self.original_formal_sig = "Unresolved" # The matching orig sig.
            self.expanded_formal_sig = "Unresolved" # Expanded version of above.
            self.actual_sig = "Unresolved" # The actual signature.

        @classmethod
        def prec(cls):
            """Return the precedence for the token.  This is currently a static
            value for each type of token.  Later it may be dynamic value
            associated with the particular tail function which is selected in a
            given context. Update: may become an attribute of a construct and
            no longer of a token."""
            return cls.static_prec

        def process_not_in_tree(self):
            """Removes any immediate children which have `not_in_tree` set."""
            modified_children = []
            for child in self.children:
                if not hasattr(child, "not_in_tree"):
                    modified_children.append(child)
                else:
                    modified_children += child.children
            self.children = modified_children

        def process_and_check_node(self, construct,
                                   val_type_override=None, all_vals_override=None,
                                   typesig_override=None):
            """This routine is automatically called just after a handler
            function returns a subtree.  It is called for the root of the
            returned subtree.  It sets some attributes and checks that the
            actual types match some defined type signature for the function.

            If `val_type_override` is set to a `TypeObject` instance then the
            return type of both the `expanded_formal_sig` and the `actual_sig`
            for the node is set to that type *after* the first pass of
            processing and type-checking for the subtree is finished.  (This
            option does not currently work for two-pass checking when
            overloading on return types is used.)  This option is useful for
            handling things like parentheses and brackets which inherit the
            type of their child (assuming the parens and brackets are kept as
            nodes in the parse tree and not eliminated).  The override value is
            used for type-checking farther up the expression tree.

            If `all_vals_override` is set to a `TypeObject` instance then all
            the possible signatures have their `val_type` changed to that type
            *before* any checking is done.  This should work for both one and
            two-pass checking, but no check is made for producing duplicate
            types due to the `val_type` changes.

            The `typesig_override` argument must be a `TypeSig` instance.  If
            set it will be *assigned* to the node as its only possible
            `expanded_formal_sig` before type checking (instead of looking up
            the registered ones).  Type checking then proceeds as usual."""

            # Get all the sigs registered for the node's construct.
            if typesig_override is not None:
                all_possible_sigs = [typesig_override]
            else:
                all_possible_sigs = construct.original_sigs
            if all_vals_override:
                all_possible_sigs = [TypeSig(all_vals_override, s.arg_types)
                                                      for s in all_possible_sigs]
            self.all_possible_sigs = all_possible_sigs # Temporary attribute.

            # Do the actual checking.
            if not self.parser_instance.overload_on_ret_types: # One-pass.
                self._check_types_one_pass()
            else: # Two-pass.
                self._check_types_first_of_two_passes()
                # If we have a *unique* matching sig, run pass two on the
                # subtree.  In this case, since the signature is fixed by
                # argument types (regardless of where the top-down pass
                # starts from) we can in this case resolve the types in the
                # subtree early.  Note `check_types_in_tree_second_pass` is
                # also called on the root node from the `parse` method.
                if len(self.matching_sigs) == 1: # matching_sigs set by _check_types
                    self.check_types_in_tree_second_pass()

            # Implement val_type override if set.
            if val_type_override:
                # Note that the original_formal_sig attribute was already set.
                # The ast_data and eval_fun are keyed on that.
                self.expanded_formal_sig = TypeSig(val_type_override,
                                                   self.expanded_formal_sig.arg_types)
                self.actual_sig = TypeSig(val_type_override, self.actual_sig.arg_types)

        def _check_types_one_pass(self):
            """Utility function called from `process_and_check_node` to check
            the actual types against their signatures when overloading is only on
            argument types."""
            all_possible_sigs = self.all_possible_sigs

            # One-pass, each child c has a unique c.expanded_formal_sig already set.
            list_of_child_sig_lists = [[c.expanded_formal_sig] for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)
            # Below all_possible_sigs is saved ONLY for printing error messages.
            self.all_possible_sigs = all_possible_sigs

            # No overloading on return types so we can finalize the actual types.
            if len(self.matching_sigs) != 1:
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution: The actual argument types match"
                        " multiple signatures.")

            # Found a unique signature; set the node's expanded_formal_sig attribute.
            # Saved sig used for eval_fun resolution, ast_data, semantic action, etc.
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type,
                                      [c.actual_sig.val_type for c in self.children])

            # Delete some temporary attributes no longer needed.
            delattr(self, "matching_sigs")
            delattr(self, "all_possible_sigs")

        def _check_types_first_of_two_passes(self):
            """Utility function called from `process_and_check_node` to do the
            first pass in checking the actual types against their signatures.
            Two-pass checking is needed for overloading on return types.  First
            pass goes up the tree, second pass goes back down."""
            all_possible_sigs = self.all_possible_sigs

            # First pass case, multiple sigs in child's self.matching_sigs list.
            list_of_child_sig_lists = [c.matching_sigs for c in self.children]

            # Reduce to only the signatures that the types of the children match.
            self.matching_sigs = TypeSig.get_all_matching_expanded_sigs(
                                      all_possible_sigs, list_of_child_sig_lists,
                                      tnode=self)

        def check_types_in_tree_second_pass(self, root=False):
            """Recursively run the second pass on the token subtree with the
            `self` node as the root.

            This method currently still needs to be explicitly called for the
            root of the final parse tree, from the `PrattParser` method
            `parse`, as well as from the checking routines here to do partial
            checks on subtrees which are already resolvable."""
            unresolved_children = [
                    c for c in self.children if hasattr(c, "matching_sigs")]
            self._check_types_pass_two() # Call first on self to do top-down.
            for child in unresolved_children: # Recurse on unprocessed children.
                child.check_types_in_tree_second_pass()
            # Delete childrens' matching_sigs lists after they are no longer needed.
            # This also acts as an indicator that the node has been resolved.
            for child in unresolved_children:
                delattr(child, "matching_sigs")
            if root:
                # The final pass in _check_types that deletes these attrs doesn't get
                # run on root, so it is explicitly done here when `root` flag is true.
                delattr(self, "matching_sigs")
                delattr(self, "all_possible_sigs")

        def _check_types_pass_two(self):
            """A second pass is only used when overloading on return types is
            allowed.  It is a top-down pass where each node chooses a unique
            final signature for each of its children.  It depends on the
            node attribute `self.matching_sigs` having been set in the first
            pass."""
            # On FIRST pass: on the way *up* the tree (after getting the
            # literal tokens, the leaves of the tree) get all the signature
            # types for a node which match in arguments for *some* possible
            # return-type choice of the children.  Same as the one-pass
            # version, but now sets of possibilities are allowed and state is
            # saved for the second pass to use: the list of matching sigs is
            # temporarily saved with the node in the self.matched_sigs
            # attribute.
            #
            # Summary: first pass, bottom-up, find all sigs that match possible
            # val_types of the node's children, across all arguments.
            #
            # After the first pass the root should have a unique sig; if not
            # there is ambiguity.  (Each node saved a set of sigs that is
            # satisfiable by some realizable choice of child sigs, and parents
            # can force children to assume any of their possible types).
            #
            # On SECOND pass: On the way *down* the tree, parents choose one
            # sig as final for each child and set it in that child's node as
            # the new self.matching_sigs.  This should always be a unique sig;
            # otherwise there is ambibuity.  Recursively called on children.
            #
            # Summary: second pass, top-down, root is unique and parents assign
            # and set the (unique) signature for each of their children.
            #
            # Note that this algorithm works just as well if the second pass is
            # run on each subtree as soon as the subtree root has a unique
            # signature, and the recursion only goes down to subtrees with
            # roots having a unique signature.  This yields partial results and
            # some error conditions sooner, and is what is implemented here.

            if len(self.matching_sigs) != 1: # The root case needs this.
                self._raise_type_mismatch_error(self.matching_sigs,
                        "Ambiguous type resolution (second pass).  Possible type "
                        "assignments for the children/arguments of the token node match"
                        " {0} possible node signatures: {1}.  Uniqueness is required."
                        .format(len(self.matching_sigs), self.matching_sigs))

            # We have a unique signature; set the node's type attributes
            self.expanded_formal_sig = self.matching_sigs[0]
            self.original_formal_sig = self.expanded_formal_sig.original_formal_sig
            # Start setting the actual signature; children will fill arg types
            # when resolved.
            self.actual_sig = TypeSig(self.expanded_formal_sig.val_type, [])

            # Set the actual_sig arg_type for the parent (appending in sequence with others).
            if self.parent is not None:
                parent_args_so_far = list(self.parent.actual_sig.arg_types)
                parent_args_so_far.append(self.expanded_formal_sig.val_type)
                self.parent.actual_sig = TypeSig(self.parent.actual_sig.val_type,
                                                 parent_args_so_far)

            # Update the matching_sigs attribute for each child (should be singleton).
            for count, child in enumerate(self.children):
                if not hasattr(child, "matching_sigs"):
                    continue # Already resolved.
                matched_sigs = TypeSig.get_child_sigs_matching_return_arg_type(
                                      child, self.expanded_formal_sig.arg_types[count],
                                      child.matching_sigs)
                # From the first pass, we know at least one child sig matches.
                assert len(matched_sigs) != 0 # Debug.
                if len(matched_sigs) > 1:
                    # Recursion could catch this on the next step, but better err msg.
                    child._raise_type_mismatch_error(matched_sigs,
                        "Token node has multiple signatures with return type matching "
                        "type of parent (pass two). Parent expects type '{0}'.  Defined"
                        " signatures are: {1}."
                        .format(self.expanded_formal_sig.val_type, child.matching_sigs))
                child.matching_sigs = matched_sigs
            return

        def _raise_type_mismatch_error(self, matching_sigs, basic_msg):
            """Raise an error, printing a helpful diagnostic message.  Assumes
            that `_check_types` has been called (to set `self.all_possible_sigs`)."""
            # TODO: Will the self.expanded_formal_sig *ever* be resolved when this routine is
            # called?  If not, then it is not very useful and message could be reworded.
            diagnostic = ("  The current token has value '{0}' and label '{1}'.  "
                         " Its expanded formal signature is {2}.  The"
                         " children/arguments have token labels and values of {3} and "
                         "value types {4}.  The list of matching signatures "
                         "is {5}.  The list of possible signatures was {6}"
                         .format(self.value, self.token_label,
                             self.expanded_formal_sig,
                             list(c.summary_repr() for c in self.children),
                             # Note this below can be "Unresolved", better message?
                             list(c.expanded_formal_sig.val_type
                                  if not isinstance(c.expanded_formal_sig, str)
                                  else c.expanded_formal_sig for c in self.children),
                             matching_sigs, self.all_possible_sigs))
            raise TypeErrorInParsedLanguage(basic_msg + diagnostic)

        #
        # Evaluations and semantic actions.
        #

        @property
        def eval_fun(self):
            """Return the evaluation function saved with the winning construct
            dispatched for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_eval_fun(orig_sig, token_value_key=self.value)

        @property
        def ast_data(self):
            """Return the ast data saved with the winning construct dispatched
            for the token.  Must be called after parsing because the
            `original_formal_sig` attribute and others must be set on the token
            instance."""
            orig_sig = self.original_formal_sig # Set during parsing.
            construct = self.construct # Set during parsing, winning construct.
            return construct.get_ast_data(orig_sig, token_value_key=self.value)

        def eval_subtree(self):
            """Run the saved evaluation function on the token, if one was
            registered with it.  Returns `None` if no evaluation function is found."""
            orig_sig = self.original_formal_sig # Set during parsing.
            eval_fun = self.eval_fun # Property method above.

            # TODO: Consider if returning None is better than raising exception...
            if not eval_fun:
                return None

            # TODO: Consider if special exception should be raised.
            #if not eval_fun:
            #    raise ParserException("An evaluation function is needed for token with "
            #            "value '{0}' and label '{1}' but no defined and matching "
            #            "evaluation function was found in the dict of eval functions.  "
            #            "The resolved original signature is {2} and the resolve expanded"
            #            " signature is {3}.  The resolved construct_label is {4}.  The "
            #            "token's eval_fun_dict is:\n   {5}."
            #            .format(self.value, self.token_label, orig_sig, sig,
            #                    self.construct_label, self.eval_fun_dict))

            return eval_fun(self)

        #
        # The main recursive_parse function.
        #

        def get_jop_token_instance(self, lex, processed_left, extra_data, subexp_prec):
            """Returns an instance of the jop token iff one should be inferred in the
            current context; otherwise returns `None`."""
            # TODO: extra_data arg now holds subexp_prec as field.
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler

            # Not if jop token is undefined for the parser.
            if not parser_instance.jop_token_subclass:
                return None

            # Not if at end of expression.
            if lex.peek().is_end_token():
                return None

            # Not if the ignored token for jop is set but not present.
            if parser_instance.jop_ignored_token_label and (
                          parser_instance.jop_ignored_token_label
                          not in lex.peek().ignored_before_labels()):
                return None

            # Now infer a jop, but only if 1) its prec would satisfy the while loop
            # in `recursive_parse` as an ordinary token, 2) the next token has
            # a head handler defined in the conditions when the jop will need
            # to run its head handler, and 3) the next token similarly has no
            # tail handler in the context.
            if parser_instance.jop_token_subclass.prec() > subexp_prec:
                # Provisionally infer a jop; create a subclass instance for its token.
                #
                # Todo: Maybe for jop and null-string tokens define methods
                # get_jop_token_instance() which gets the token but calls the
                # lexer to dress it up more like a "real" token, with ignored_before
                # and line numbers, etc. (without putting it in the buffer, of course).
                jop_instance = parser_instance.jop_token_subclass(None)
                jop_instance.extra_data = extra_data

                # This is a little inefficient (since it uses a `go_back` call)
                # but we need to be sure that when the tail handler of the jop
                # is called and it reads a token that that token has a head
                # handler defined for it *in that precondition context*.
                # Otherwise, no jop will be inferred.  We also make sure that
                # it has no tail handler in the context, since then it would be
                # a lower-precedence (lower precedence because we broke out of
                # the loop above) infix or postfix operator, and no jop is
                # inferred before another operator).
                curr_token = lex.next()
                try:
                    # Dispatch here WITHOUT CALLING, since calling will consume
                    # another token; also, deeper-level recursions could cause false
                    # results to come up the recursion chain.  We are just testing
                    # what handlers are defined for the token.
                    _peek_head_handler, head_construct = dispatch_handler(
                                                   HEAD, curr_token, lex, extra_data)
                    try: # Found head handler, now make sure it has no tail handler.
                        _peek_tail_handler, tail_construct = dispatch_handler(
                                   TAIL, curr_token, lex, extra_data, processed_left)
                    except NoHandlerFunctionDefined:
                        # This is the only case where an actual token is returned.
                        return jop_instance
                    else:
                        return None
                except NoHandlerFunctionDefined:
                    return None # No precondition matches, assume no jop.
                finally:
                    #delattr(curr_token, "extra_data") # Only needed if pushback below, not go_back.
                    lex.go_back(1)
            else:
                return None

        def dispatch_null_string_handler(self, head_or_tail, lex, subexp_prec,
                                         extra_data, processed_left=None):
            """Check for any possible matching null-string token handlers;
            return the token and the matching handler if one is found.

            Note that the precedence for a null-string token is set to
            `subexpr_prec`, so it would always have activated the while loop if
            it were a real token."""
            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            # See if a null-string token is set and a handler matches preconds.
            if not parser_instance.null_string_token_label:
                return None, None, None
            else:
                # TODO: Later don't re-create each time, save one.
                null_string_token = parser_instance.null_string_token_subclass(None)
            null_string_token.extra_data = extra_data

            curr_token = None
            handler_fun = None
            construct = None
            try:
                handler_fun, construct = dispatch_handler(head_or_tail,
                                                          null_string_token,
                                                          lex, extra_data, processed_left)
                curr_token = null_string_token
            except NoHandlerFunctionDefined:
                pass
            return curr_token, handler_fun, construct

        def recursive_parse(self, subexp_prec, only_head=False):
            """Parse a subexpression as defined by token precedences. Return
            the result of the evaluation.  Recursively builds up the final
            result in `processed_left`, which is the tree for the part of the
            full expression to the left of the current token.

            The list `lookbehind` saves all the previously evaluated
            subexpressions at this level of recursion (i.e., at the top level
            in the same subexpression) and passes it to the dispatched tail
            handlers, in case that routine wants to make use of it.  For
            example, the ordinal position of the token in the top level of the
            subexpression can be calculated from the length of `lookbehind`.

            This function is made a method of `TokenSubclass` so that handler
            functions can easily call it by using `tok.recursive_parse`, and
            also so that it can access the lexer without it needing to be
            passed as an argument.  It is basically a static function,
            though.

            The `extra_data` attribute is set for all triggering tokens, and is
            guaranteed to be available for precondition functions and for
            handler functions.  It is set before any dispatches or recursive calls,
            and is deleted from the token after the recursive call.  It is an
            advanced feature which most users will not need."""
            # Note that all the dispatching functions set the `extra_data`
            # attribute of their token before the dispatching is done, but they
            # do not update `extra_data` itself in any way.

            # Note on below code: It is tempting for efficiency to define a jop
            # and null-string token instance, save it, and only use it when
            # necessary (replacing it only when used).  But some things need to
            # be considered.
            #
            # Now that handlers are not with tokens, that is no longer a
            # concern... TODO go ahead and do this.
            #
            # Is there any special attribute or other thing that is assigned on
            # creation which might change?  Either way, you should probably add
            # extra things like line numbers to mimic ordinary tokens. Note
            # that currently you only really pay the creation cost if you
            # actually use the jop or null-string feature, but a lot of dummy
            # instances are created if you do.

            # This err check catches some cases of tokens defined via Lexer, not all.
            if not hasattr(self, "token_kind"):
                raise ParserException("All tokens used in the parser must be"
                        " defined in via parser's methods, not the lexer's.")

            #
            # Initialize, and set some shorter aliases.
            #

            parser_instance = self.parser_instance
            dispatch_handler = parser_instance.construct_table.dispatch_handler
            lex = self.token_table.lex
            extra_data = ExtraDataTuple(lookbehind=[], constructs=[],
                                        subexp_prec=subexp_prec)

            #
            # Start the actual Pratt parsing recursion.
            #

            curr_token, head_handler, construct = self.dispatch_null_string_handler(
                                                     HEAD, lex, subexp_prec, extra_data)
            if not curr_token: # No null-string token fired, so use normal next() call.
                curr_token = lex.next()
                head_handler, construct = dispatch_handler(
                                                     HEAD, curr_token, lex, extra_data)

            extra_data.constructs.append(construct)

            # TODO: Should the root of processed_left be set for is_head instead, for
            # general case?  Or set "head_trigger_token" to label instead of None?
            # Consider how lookup will work in usual and general cases of arbitrary
            # token as subtree root.
            curr_token.is_head = True # Used to look up eval_fun and ast_data later.

            processed_left = head_handler()

            delattr(curr_token, "extra_data") # Delete after recurse, allow mem cleanup.
            extra_data.lookbehind.append(processed_left)
            extra_data.constructs.append(construct)

            if only_head:
                return processed_left

            while True:

                #
                # The loop below is the main loop in ordinary Pratt parsing.  The
                # Outer loop is ONLY for the special case when a jop is defined.
                #

                # TODO: Consider modification like code below to allow
                # precedences per constuct, which also makes "prec - 1" no
                # longer necessary for right assoc when property is set for the
                # construct itself.  See what performance hit it has, one
                # go_back per subexpression.  Note that jops use a single
                # go_back already when they are defined...
                #
                # The ugly comment-string code below works.  It just pulls the
                # token-dispatching out to before the precedence test.
                # Obviously could then use some cleanup and refactoring, too.
                # Consider possible interactions with jop and null-string
                # tokens, but they don't do a `next` call anyway.  (Is it
                # better to pull out the ns_token dispatch, at least?  In
                # regular code, how to get null-string to appear at end of a
                # subexpression?)
                #
                # Argument it works: This code is doing exactly the same
                # dispatching as it would inside the loop test, but it is doing
                # it before the loop test.  The loop test never modifies
                # anything.  If the test fails the effects of the dispatches
                # are undone.
                """
                while True:
                    #err = None
                    ns_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if ns_token:
                        curr_token = ns_token
                        peek_prec = lex.token.prec()
                        #peek_prec = construct.prec() # Switch to this...
                    else:
                        curr_token = lex.next()
                        try:
                            tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                            lex, extra_data, processed_left)
                            peek_prec = lex.token.prec()
                            #peek_prec = construct.prec() # Switch to this...
                        except NoHandlerFunctionDefined as e:
                            # If no construct at all then can't have tail handler so
                            # prec should be 0.  But if it fails due to a precond,
                            # token itself could still have a prec > 0.  In that case
                            # it will get inside the loop and fail, but it really
                            # shouldn't have gotten inside.
                            #
                            # Only one test changes, and new one is commented out in
                            # the test file under the old one.
                            #err = e
                            peek_prec = -1 # Always fail test and break.
                            #peek_prec = lex.token.prec()

                    #test_assoc = False if err else (peek_prec == subexp_prec and
                    #                                construct.assoc == "right")
                    test_assoc = peek_prec == subexp_prec and construct.assoc == "right"
                    if peek_prec > subexp_prec or test_assoc:
                        #if err: # Error would have been found inside loop, now above.
                        #    raise err # Avoid error msg changing (makes test fail).
                        processed_left = tail_handler()
                        delattr(curr_token, "extra_data")
                        extra_data.lookbehind.append(processed_left)
                        extra_data.constructs.append(construct)
                    else:
                        if not ns_token:
                            lex.go_back(1)
                        break
                """

                while lex.peek().prec() > subexp_prec:

                    curr_token, tail_handler, construct = self.dispatch_null_string_handler(
                                    TAIL, lex, subexp_prec, extra_data, processed_left)
                    if not curr_token: # No null handler fired off, get regular way.
                        curr_token = lex.next()
                        tail_handler, construct = dispatch_handler(TAIL, curr_token,
                                                        lex, extra_data, processed_left)

                    processed_left = tail_handler()
                    delattr(curr_token, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)

                #
                # Broke out of main loop, determine whether or not to infer a jop.
                #

                jop_instance = self.get_jop_token_instance(
                                         lex, processed_left, extra_data, subexp_prec)
                if jop_instance:
                    jop_tail_handler, construct = dispatch_handler(TAIL, jop_instance,
                                                        lex, extra_data, processed_left)
                    processed_left = jop_tail_handler()
                    delattr(jop_instance, "extra_data")
                    extra_data.lookbehind.append(processed_left)
                    extra_data.constructs.append(construct)
                else:
                    break

            return processed_left

        #
        # Copying instances of tokens.
        #

        def __copy__(self):
            """Return a shallow copy of the token."""
            return copy.copy(self)

        #
        # Some representations that apply to the subclasses.
        #

        def summary_repr_with_types(self):
            """A short summary repr of the node, without its children."""
            return ("<" + str(self.token_label) +
                    ",'" + str(self.value) +
                    "'," + str(self.expanded_formal_sig.val_type) + ">")

        def tree_repr_with_types(self, indent=""):
            """Token representation as the root of a parse subtree, with formatting.
            The optional `indent` parameter can be either an indent string or else
            an integer for the number of spaces to indent.  Note that the ordinary
            `tree_repr` method without types is also available, inherited from
            the base node object."""
            try:
                num_indent = int(indent)
            except ValueError:
                pass
            else:
                indent = " " * num_indent
            string = indent + self.summary_repr_with_types() + "\n"
            for c in self.children:
                string += c.tree_repr_with_types(indent=indent+" "*4)
            return string

        def string_repr_with_types(self):
            """A string repr for the tree that includes type information."""
            string = self.summary_repr_with_types()
            if self.children:
                string += "("
                string += ",".join(c.string_repr_with_types() for c in self.children)
                string += ")"
            return string

        @classmethod
        def class_repr(cls):
            """Print out the `TokenSubclass` classes (representing tokens) in a
            nice way.  The default is hard to read."""
            string = "Token({0})".format(cls.token_label)
            return string

    return TokenSubclass # Return from token_subclass_factory function.

#
# Parser
#

def lexer_add_parser_instance_attribute(lexer, token):
    """Passed to lexer to add a `parser_instance` attribute to each token it
    returns.  This attribute is added to instances at the lexer, from its
    current token table, because of the case where parsers call other parsers.
    (It is not added to general token subclasses in `def_token_master` because
    parsers could potentially share token subclasses.)"""
    token.parser_instance = lexer.token_table.parser_instance # From token table.
    return token

# Could also add parser_instance and construct as fields of the extra data tuple.
# Could extra_data also be passed to handler functions?  Nice to have construct
# instance available there, perhaps.  TODO: Consider.
ExtraDataTuple = namedtuple("ExtraHandlerData", ["lookbehind",
                                                 "constructs",
                                                 "subexp_prec"])

class PrattParser(object):
    """A parser object.  Each parser object contains a table of defined tokens,
    a lexer, a table of constructs, and a table of defined types."""
    def __init__(self, max_peek_tokens=None,
                       max_deque_size=None,
                       lexer = None,
                       default_begin_end_tokens=True,
                       type_table = None,
                       skip_type_checking=False,
                       overload_on_arg_types=True,
                       overload_on_ret_types=False,
                       partial_expressions=False,
                       parser_label=None,
                       raise_on_equal_priority_preconds=False):
        """Initialize the parser.

        The `max_peek_tokens` parameter is an optional arbitrary limit on the
        level of peeks allowed in the lexer.  Setting to 1 limits it to a
        single token lookahead.  The default setting `None` gives
        peek-on-demand as far ahead as requested.

        The `max_deque_size` parameter is an optional limit on the size of the
        deque that the lexer keeps for previous tokens, the current token, and
        requested peek tokens.  The default is for it to grow arbitrarily
        (though it is reset on each parse).  Needs to be large enough for the
        max level of peeks required plus the max `go_back` level required.

        If a `Lexer` instance is passed in the parser will use that lexer and
        its token table, otherwise a new lexer is created.  The any other lexer
        options are ignored.

        No default begin and end functions will be set if a lexer is passed in,
        regardless of the value of `default_begin_end_tokens`.  Otherwise,
        default begin and end tokens will be defined unless
        `default_begin_end_tokens` is set false (note that creating them by
        default is the opposite of the default behavior for the lower-level
        Lexer class).

        Setting `skip_type_checking=True` is slightly faster since typing is
        not being used at all.  Note that overloading depends on type-checking
        to resolve the actual types, so this flag implies that the overload
        flags are all false.  The default is false.  It should be possible to
        define types, use them during testing, and then turn checking off ---
        provided overloading is not used to get different evaluation functions
        or AST data elements for different overloads.

        The `overload_on_arg_types` flag specifies whether or not to overload
        on argument types.  The default is true.  Cannot be changed after
        initialization.

        Setting `overload_on_ret_types` also overloads on argument types.  It
        requires an extra walk of the token tree, and implies overloading on
        argument types.  The default is false.  Cannot be changed after
        initialization.

        If `partial_expressions` is set true then no check will be made in the
        `parse` method to see if the parsing consumed up to the end-token in
        the lexer.  Multiple expression text can be parsed by repeatedly
        calling `parse` when this option is true and checking whether the
        lexer's current token is the end-token.

        The `parser_label` is an optional descriptive string for a parser.
        These can be useful in debugging when they appear in error messages,
        especially when working with multiple parser instances.

        If `raise_on_equal_priority_preconds` is true then an exception will be
        raised if two precondition functions are registered with the same
        trigger token in the same head or tail position which have the same
        precondition priority.  The default is false, and the first-defined
        matching precondition function of the same priority will win any
        competition when several are true.  This option can be used to ensure
        at language define-time that there is no definition-order dependence in
        dispatching.  If two such preconditions functions are mutually
        exclusive there is no problem with them having the same priority, but
        this condition cannot be checked by a program.  A small difference can
        be added."""

        if parser_label:
            self.parser_label = parser_label # Set first, for error messages.
        else:
            self.parser_label = None

        ## Type-checking options below; these cannot be changed after initialization.
        if overload_on_ret_types:
            overload_on_arg_types = True # Overload on ret implies overload on args.
        self.skip_type_checking = skip_type_checking # Skip all type checks, faster.
        if not skip_type_checking:
            self.overload_on_arg_types = overload_on_arg_types
            self.overload_on_ret_types = overload_on_ret_types
        else: # Overloading requires type checking.
            self.overload_on_arg_types = False
            self.overload_on_ret_types = False

        # If exceptions are not raised on ties then with non-mutually-exclusive
        # precond functions the first-set one will have precedence when they
        # are both true.  Need to define this before registering any handlers (
        # which is done below in `def_begin_end_tokens`).
        self.raise_on_equal_priority_preconds = raise_on_equal_priority_preconds
        #self.raise_on_equal_priority_preconds = True # DEBUG

        self.construct_table = ConstructTable(parser_instance=self) # Dict of constructs.
        self.default_construct_label_number = 0 # For unique precondition labels.

        if lexer: # Lexer passed in.
            self.lex = lexer
            self.token_table = lexer.token_table
        else: # No Lexer passed in.
            self.token_table = TokenTable(
                                token_subclass_factory_fun=token_subclass_factory)
            self.lex = Lexer(self.token_table,
                             max_peek_tokens=max_peek_tokens,
                             max_deque_size=max_deque_size,
                             default_begin_end_tokens=False)
            # Set the begin and end tokens unless the user specified not to.
            if default_begin_end_tokens:
                self.def_begin_end_tokens() # Use function's defaults.
        self.lex.default_helper_exception = ParserException # Default for match_next, etc.
        # Add mod function to lexer here, works even if they passed in a lexer.
        self.lex.final_mod_function = lexer_add_parser_instance_attribute

        self.token_table.parser_instance = self # Give token table ref to parser.

        if type_table:
            self.type_table = type_table
        else:
            self.type_table = TypeTable(self)

        self.num_lookahead_tokens = max_peek_tokens
        self.jop_token_label = None # Label of the jop token, if any.
        self.jop_token_subclass = None # The actual jop token, if defined.
        self.null_string_token_label = None # Label of the null-string token, if any.
        self.null_string_token_subclass = None # The actual null-string token, if any.

        self.partial_expressions = partial_expressions # Whether to parse multiple expressions.

        self.pstate_stack = [] # Stack of production rules used in grammar parsing.
        self.top_level_production = False # If true, require grammar parses to consume to end.
        self.disable_pstate_processing = False # Set to temporarily disable grammar parsing.

    #
    # Methods defining tokens.
    #

    def def_token_master(self, token_label, regex_string=None, on_ties=0, ignore=False,
                         token_kind="regular", ignored_token_label=None,
                         matcher_options=None):
        """The master method for defining tokens; all the convenience methods
        actually call it.  Allows for factoring out some common code and
        keeping the attributes of all the different kinds of tokens up-to-date.
        This routine calls the underlying lexer's `def_token` to get tokens and
        then adds extra attributes needed by the `PrattParser` class.

        The `token_kind` argument must be one of the following strings:
        `"regular"`, `"ignored"`, `"begin"`, `"end"`, `"jop"`, or
        `"null-string"`.  The `ignored_token_label` is used only when defining
        a jop.

        Tokens can be shared between parsers if all their properties are the
        same.  Note that for now this includes the precedence value for any
        tail handlers (since that is made a token attribute).  Null-string and
        jop tokens are the exception, but they are special in that they are
        never returned by the lexer, only by a particular parser."""
        token_table = self.token_table

        if token_kind == "regular":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=ignore, matcher_options=matcher_options)

        elif token_kind == "ignored":
            tok = token_table.def_token(token_label, regex_string,
                       on_ties=on_ties, ignore=True, matcher_options=matcher_options)

        elif token_kind == "begin":
            tok = token_table.def_begin_token(token_label)
            self.begin_token_label = token_label
            # Define dummy handlers for the begin-token, just to catch errors.
            def begin_head(self, lex):
                """Dummy head handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called head-handler for begin token.")
            def begin_tail(self, lex, left):
                """Dummy tail-handler for begin-tokens."""
                raise CalledBeginTokenHandler("Called tail-handler for begin token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, begin_head, token_label)
            self.def_construct(TAIL, begin_tail, token_label, dummy_handler=True)
            self.begin_token_subclass = tok

        elif token_kind == "end":
            tok = token_table.def_end_token(token_label)
            self.end_token_label = token_label
            # Define dummy handlers for the end-token, just to catch errors.
            def end_head(self, lex):
                """Dummy head handler for end-tokens."""
                raise CalledEndTokenHandler("Called head-handler for end token.")
            def end_tail(self, lex, left):
                """Dummy tail-handler for end-tokens."""
                raise CalledEndTokenHandler("Called tail-handler for end token.")
            tok.token_kind = token_kind # Needed before calls to def_construct.
            self.def_construct(HEAD, end_head, token_label)
            self.def_construct(TAIL, end_tail, token_label, dummy_handler=True)
            self.end_token_subclass = tok

        elif token_kind == "jop":
            if self.jop_token_subclass:
                raise ParserException("A jop token is already defined.  It must be "
                                      "undefined before defining a new one.")
            self.jop_token_label = token_label
            self.jop_ignored_token_label = ignored_token_label
            tok = token_table.def_token(token_label, None)
            self.jop_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        elif token_kind == "null-string":
            if self.null_string_token_subclass:
                raise ParserException("A null-string token is already defined.  It"
                         " must be undefined before defining an new one.")
            self.null_string_token_label = token_label
            tok = token_table.def_token(token_label, None)
            self.null_string_token_subclass = tok
            tok.parser_instance = self # Special token, never returned by lexer.

        else:
            raise ParserException("Bad call to def_token_master, with unrecognized"
                    ' string "{0}" for the keyword argument token_kind.'
                    .format(token_kind))

        tok.token_kind = token_kind
        tok.is_head = False # Set true in recursive_parse if instance parses as a head.
        return tok

    def def_token(self, token_label, regex_string, on_ties=0, ignore=False,
                  matcher_options=None):
        """Define a token.  Use this instead of the Lexer `def_token` method,
        since it adds extra attributes to the tokens."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore,
                              token_kind="regular", matcher_options=matcher_options)

    def def_ignored_token(self, token_label, regex_string, on_ties=0,
                          matcher_options=None):
        """A convenience function to define a token with `ignored=True`."""
        return self.def_token_master(token_label, regex_string, on_ties, ignore=True,
                              token_kind="ignored", matcher_options=matcher_options)

    def def_begin_end_tokens(self, begin_token_label="k_begin",
                                   end_token_label="k_end"):
        """Calls the `Lexer` method to define begin- and end-tokens.  The
        subclasses are then given initial head and tail functions for use in
        the Pratt parser.  To use the `PrattParser` this method must be called,
        not the method of `Lexer` with the same name (since it also creates
        head and tail handler functions that raise exceptions for better error
        messages).  The default is to call this method automatically on
        initialization, with the default token labels for the begin and end
        tokens.  If the flag `default_begin_end_tokens` is set false on
        `PrattParser` initalization then the user must call this function
        (setting whatever token labels are desired).  Returns a tuple
        containing the new begin and end `TokenNode` subclasses."""
        begin_tok = self.def_token_master(begin_token_label, token_kind="begin")
        end_tok = self.def_token_master(end_token_label, token_kind="end")
        return begin_tok, end_tok

    def def_jop_token(self, jop_token_label, ignored_token_label):
        """Define a token for the juxtaposition operator.  This token has no
        regex pattern.  An instance is inserted in `recursive_parse` when it is
        inferred to be present.  This method must be explicitly called before a
        juxtaposition operator can be used (i.e., before `def_jop`).  The
        parameter `jop_token_label` is the label for the newly-created token
        representing the juxtaposition operator.  The `ignored_token_label`
        parameter is the label of an ignored token which must be present for a
        jop to be inferred.  Some already-defined token is required; usually it
        will be a token for spaces and tabs.  If set to `None` then no ignored
        space at all is required (i.e., the operands can be right next to each
        other)."""
        return self.def_token_master(jop_token_label,
                                     ignored_token_label=ignored_token_label,
                                     token_kind="jop")

    def def_null_string_token(self, null_string_token_label="k_null-string"):
        """Define the null-string token.  This token has no regex pattern.  An
        instance is inserted in `recursive_parse` when it is inferred to be
        present based.  This method must be called before a
        null-string can be used.  The parameter `null_string_token_label` is
        the label for the newly-created tok representing it."""
        return self.def_token_master(null_string_token_label,
                                     token_kind="null-string")

    def get_token(self, token_label):
        """Return the token with the label `token_label`.  The reverse
        operation, getting a label from a token instance, can be done by
        looking at the `token_label` attribute of the token."""
        return self.token_table[token_label]

    #
    # Undefine tokens.
    #

    def undef_token(self, token_label):
        """A method for undefining any token defined by the `PrattParser` methods.
        Since the `token_kind` was set for all tokens when they were defined
        it knows how to undelete any kind of token."""
        # TODO: Make sure this is up-to-date with the what the token_master class does.
        token_table = self.token_table
        tok = token_table[token_label]
        kind = tok.token_kind
        if kind == "jop":
            token_table.undef_token(self.jop_token_label)
            self.jop_token_subclass = None
            self.jop_token_label = None
            self.jop_ignored_token_label = None
        elif kind == "null-string":
            token_table.undef_token(self.null_string_token_label)
            self.null_string_token_subclass = None
            self.null_string_token_label = None
            self.null_string_ignored_token_label = None
        else:
            token_table.undef_token(token_label)

    #
    # Methods to define and undefine constructs.
    #

    def def_construct(self, head_or_tail, handler_fun, trigger_token_label,
                      prec=0, construct_label=None, precond_fun=None,
                      precond_priority=0, val_type=None, arg_types=None,
                      eval_fun=None, ast_data=None, token_value_key=None,
                      dummy_handler=False):
        """Define a construct and register it with the token with label
        `trigger_token_label`.  A token with that label must already be in the
        token table or an exception will be raised.

        Stores the construct instance in the parser's construct table and also
        return the construct instance.

        The `head_or_tail` argument should be set to either `HEAD` or `TAIL`.
        If `head_or_tail==TAIL` then the operator precedence will be set to
        `prec`.  For a head handler the `prec` value is ignored and effectively
        set to zero.  For a tail handler a `prec` value greater than zero is
        required or else an exception will be raised (unless `dummy_handler` is
        set true).  Similarly, an exception is raised for a non-zero `prec`
        value for a head-handler (the default value).

        The `construct_label` is an optional string value which can result in
        better error messages.

        The `eval_fun` and the `ast_data` arguments are saved in dicts
        associated with the type signature.

        If `token_value_key` is set to a string value then that value will be
        part of the key tuple for saving AST data and evaluation functions.
        This can be used, for example, when overloading a generic identifier
        with different evaluation functions for when the identifier value is
        `sin`, `cos`, etc.  In looking up the AST data and evaluation function
        the parsed token's actual string value (from the program text) is used
        as the key.  If any overload of a particular construct provides a
        `token_value_key` string then all the other overloads for that
        construct must also (for the time being, at least)."""
        # Note that the parser_instance attribute of tokens is not necessarily
        # set yet when this method is called.
        if isinstance(arg_types, str):
            raise ParserException("The arg_types argument to token_subclass must"
                    " be None or an iterable returning type labels (e.g., a list"
                    " or tuple).")

        if head_or_tail == TAIL and prec <= 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a tail hander and a precedence of zero or less."
                    .format(trigger_token_label))
        if head_or_tail == HEAD and prec != 0 and not dummy_handler:
            raise ParserException("Attempt to define a construct for trigger token"
                    " '{0}' with a head hander and a precedence not equal to zero."
                    .format(trigger_token_label))

        if precond_fun is None:
            precond_fun = DEFAULT_ALWAYS_TRUE_PRECOND_FUN

        if trigger_token_label in self.token_table:
            trigger_token_subclass = self.get_token(trigger_token_label)
        else:
            raise ParserException("In call to def_construct: subclass for"
                    " token labeled '{0}' has not been defined.  Maybe try"
                    " calling def_token first.".format(trigger_token_label))
            # Below line formerly just created a subclass, but that can mask errors!
            #TokenSubclass = self.token_table.create_token_subclass(token_label)

        if not hasattr(trigger_token_subclass, "token_kind"):
            raise ParserException("Token with label '{0}'  must be defined by the"
                                  " parser's def_token method, not the lexer's method."
                                  .format(trigger_token_label))

        # TODO: Precedence is currently saved as a token attribute.  Consider
        # saving it in the construct instead.  See main Sphinx docs, unimplemented
        # generalizations.
        if head_or_tail == TAIL:
            if (trigger_token_subclass.static_prec != 0 and
                    prec != trigger_token_subclass.static_prec):
                raise ParserException("Redefining the precedence of the triggering"
                        " token subclass '{0}' to a new value {1} not equal"
                        " to the previous nonzero value of {2}."
                        " The original precedence will never be used.  To actually"
                        " reset the value, set trigger_token_label.static_prec=0"
                        " explicitly before this call to def_construct.  Currently"
                        " all operators with the same triggering token must have"
                        " the same precedence value, regardless of preconditions."
                        .format(trigger_token_label, prec,
                                trigger_token_subclass.static_prec))
            trigger_token_subclass.static_prec = prec # Ignore prec for heads; will stay 0.

        # Create the type sig object.
        if self.skip_type_checking:
            type_sig = None
        else:
            type_sig = TypeSig(val_type, arg_types)

        # Register the handler funs.
        construct = self.construct_table.register_construct(
                                          head_or_tail=head_or_tail,
                                          trigger_token_subclass=trigger_token_subclass,
                                          handler_fun=handler_fun,
                                          precond_fun=precond_fun,
                                          precond_priority=precond_priority,
                                          construct_label=construct_label,
                                          type_sig=type_sig,
                                          eval_fun=eval_fun,
                                          ast_data=ast_data,
                                          token_value_key=token_value_key)
        return construct

    def undef_construct(self, construct, type_sig=None, token_value_key=None):
        """Undefine a construct.  If `type_sig` is passed a `TypeSig` instance then
        only that overload is deleted.  If `token_value_key` is also defined then
        only that token key is unregistered.  Otherwise the full construct is
        removed from the parser's construct table."""
        # Note users themselves could unregister the overloads if they have the
        # construct instance.
        self.construct_table.unregister_construct(construct, type_sig, token_value_key)

    #
    # Methods dealing with types.
    #

    def def_type(self, type_label):
        """Define a type associated with the name `type_label`."""
        return self.type_table.create_typeobject(type_label)

    def undef_type(self, type_label):
        """Undefine the type associated with the name `type_label`."""
        self.type_table.undef_typeobject(type_label)

    #
    # The main parse routines.
    #

    def parse_from_lexer(self, lexer_to_use, pstate=None):
        """The same as the `parse` method, but a lexer_to_use is already assumed to be
        initialized.  This is ONLY used when one parser instance calls another
        parser instance (implicitly, via the handler functions of its tokens).
        The outer parser calls this routine of the inner, subexpression parser.
        Such a call to another parser would look something like::

            alternate_parser.parse_from_lexer(lexer_to_use)

        where `lexer_to_use` is the lexer_to_use of the outer parser.  This routine
        temporarily swaps the token table for the passed-in lexer_to_use to be the
        token table for this parser (remember that this parser is the inner
        parser when this routine is called)."""
        # Note you do not need to set the type_table, since the tokens always
        # have fixed references to their own parser instance.

        # Set up to read from lexer_to_use, after setting its token table to
        # be the token table for this parser (this is the inner parser).

        # Temporarily change new lexer's token table.
        lexer_to_use_usual_table = lexer_to_use.token_table
        lexer_to_use.set_token_table(self.token_table)

        # Swap the lexer in.
        usual_lexer = self.lex
        self.lex = lexer_to_use # Swap the lexer.

        try:
            parsed_subexpression = self.parse("IGNORED", pstate=pstate,
                                    partial_expressions=True,
                                    skip_lex_setup=True)
        except ParserException:
            print("Error in `parse_from_lexer` method, in call to `parse` method"
                    " using a different parser's lexer for a subexpression.",
                    file=sys.stderr)
            raise
        finally:
            # Restore the temporary lexer's token table.
            lexer_to_use.set_token_table(lexer_to_use_usual_table)
            self.lex = usual_lexer
        return parsed_subexpression

    def parse(self, program, pstate=None, partial_expressions=None,
                                                      skip_lex_setup=False):
        """The main routine for parsing a full program or expression.  Users of
        the class should call this method to perform the parsing operations
        (after defining a grammar, of course).

        Unless there was a parsing failure or `partial_expressions` is true
        then the lexer is left with the end-token as the current token.

        If the `pstate` variable is set then the value will be pushed as the
        initial state on the production rule stack `pstate_stack`.  The stack
        is then cleared after a successful call.  (Set the parser attribute
        directly for more control.)

        The parser's `partial_expressions` attribute will be used unless it is
        overridden by the parameter `partial_expressions` here.  When it is
        true no check is made for the end-token after `recursive_parse` returns
        a value.    The lexer will be left at the last token consumed, so a
        check for the end-token will tell when all the text was consumed.
        Users are responsible for making sure their grammars are suitable for
        this kind of parsing if the option is set.

        If the `skip_lex_setup` parameter is true then the text `program` is
        ignored and lexer setup is skipped.  This is generally ONLY used when
        multiple parsers are parsing from a common text stream, and `parse` is
        called from the method `parse_from_lexer`."""
        if pstate:
            self.pstate_stack = [pstate] # For parsing production rule grammars.
        if partial_expressions is None:
            partial_expressions = self.partial_expressions

        if not skip_lex_setup:
            self.lex.set_text(program)
        begin_tok = self.lex.token # Get the first token to access recursive_parse.
        parse_tree = begin_tok.recursive_parse(0)

        # Finalize type-checking for root when overloading on return types.
        if self.overload_on_ret_types:
            parse_tree.check_types_in_tree_second_pass(root=True)

        # See if we reached the end of the token stream.
        if not self.lex.peek().is_end_token() and not partial_expressions:
            raise IncompleteParseException("Parsing never reached the end of"
                " the text.  Parsing stopped with tokens still in the lexer."
                "  No syntax element was recognized. The last-parsed token had"
                " value '{0}' and label '{1}'.  Parsing stopped before a token"
                " in the lexer with value '{2}' and label '{3}'.  The partial"
                " result returned is:\n{4}"
                .format(self.lex.token.value, self.lex.token.token_label,
                        self.lex.peek().value, self.lex.peek().token_label,
                        parse_tree.tree_repr()))

        if pstate:
            self.pstate_stack = []
        return parse_tree

#
# Copy the convenience functions from builtin_parse_methods to the PrattParser class.
#

for method in builtin_parse_methods.parse_methods:
    setattr(PrattParser, method.__name__, method)

for method in predefined_token_sets.token_defining_methods:
    setattr(PrattParser, method.__name__, method)

#
# Exceptions
#

class IncompleteParseException(ParserException):
    """Only raised at the end of the `PrattParser` function `parse` if tokens
    remain in the lexer after the parser finishes its parsing."""
    pass

