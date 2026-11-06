---
name: code-style
description: Rules for the shape of new and changed Python code in this repository. Covers pure functions and immutable data (frozen dataclasses), values derived once at construction, small functions and files (100 and 1000 lines), orchestration functions that read like pseudocode, large classes as thin orchestrators whose __init__ is a sequence of _init_* helpers, composition instead of mixins, protected names by default, keyword arguments, narrow parameters instead of whole objects, direct attribute access instead of defensive getattr/hasattr, and no dead code or compatibility shims. Adapted from the SGLang code-style rules. Use it whenever you write, refactor or review Python code under src/. For comments and docstrings, use code-comments. For tests, use testing.
---

# Code style

These rules are the default for new and changed Python code. Follow them unless there is a
concrete reason not to. If you do not follow a rule, tell the user why.

The rules are adapted from the SGLang rules `general-code-style.md`, `no-getattr-defensive.md` and
`no-dataclasses.md` (`.claude/rules/` in https://github.com/sgl-project/sglang), and from the
SGLang `large-class-style` skill (`.agents/skills/` in the same repository). The dead-code rules
come from the owner of this repository.

## Data and state

- **Prefer pure functions.** Pass the inputs in and return the outputs. Do not write a method that
  changes instance state when a function of plain values can do the same work. A pure function
  is also easy to test (see the testing skill).
- **Prefer immutable data.** Define a data container as `@dataclass(frozen=True)`, like most
  containers in `src/`. Use a tuple or a frozenset for a collection that does not change. Make a
  container mutable only when code must change it in place.
- **Derive a fixed value once.** Sometimes the inputs of a derived value do not change for the
  life of the object, for example constructor arguments, environment variables or a config. Then
  compute the value in `__init__` or `__post_init__`, and store it in an attribute with a clear
  name. Later code reads the attribute. If the inputs can change, compute the value where the
  code uses it. If you cannot give the value a meaningful name, do not store it.

## Size and structure

- **Keep each function at 100 lines or fewer.** Split a longer function into helpers with clear
  names.
- **Keep each file at 1000 lines or fewer.** Split a larger module along the boundaries of its
  responsibilities.
- **Keep each package at 10 files or fewer.** `gate/checks/src_layout.py` checks this limit.
- A class has no line limit of its own. The file limit bounds it, and
  [Large classes](#large-classes) keeps it thin.
- **Make the main function read like pseudocode.** The top-level function of a unit is short.
  Each step is a call to a helper with a clear name, so that the reader sees the flow first.
- **Use composition, not mixins.** Hold a collaborator and call it, or call a plain function. Do
  not add behavior through a mixin class.

## Interfaces

- **Make names protected by default.** Start the name of a function, a method or an attribute
  with `_`, unless code outside its module or class uses it.
- **Call by keyword.** When a function takes two or more arguments, pass them by keyword. In a
  new function, put `*` before each parameter whose meaning is not clear from its position.
- **Pass what the callee needs, not the whole object.** Pass the specific values by keyword, not
  a whole `argparse.Namespace`, `Store` or runner. Pass the whole object only to a leaf whose
  contract needs it. Then the leaf only reads the object, and it returns its results. The caller
  assigns them.

  Example: `trial_config(args, ...)` in an earlier `methods/evaluate.py` took a whole
  `argparse.Namespace`. `methods/gate.py` called it with a namespace from a different parser. So
  `evaluate.py` read some flags with `getattr(args, name, default)`, and no reader could see which
  caller set which flag.

## Large classes

These rules apply to a class that coordinates other parts, such as `Driver` in
`rl_driver/driver.py`, `Worker` in `worker/attempts.py` or `Orchestrator` in `worker/run/runner.py`.
They do not apply to a data container or a small utility class.

A class that holds only orchestration shows its parts and their order in one place. Each part can
then be read and tested alone. A class that mixes in domain logic grows into a god class.

### Orchestration only

Each statement in a large class does one of these with a collaborator:

1. **Construct** it, in a short `_init_<thing>` helper.
2. **Wire** it, by calling that helper from `__init__`.
3. **Delegate** to it, with a call such as `self._store.claim(...)`.
4. **Coordinate** the calls: an `if` that chooses which collaborator to call, the order of the
   calls, or the result of one call passed into the next.

A statement that computes or transforms a value, beyond passing arguments and results through, is
domain logic. Examples are building a config, transforming data, an algorithm, arithmetic and
post-processing. Move domain logic into a collaborator in its own module, or into a pure function.

Coordination that you cannot extract as one cohesive unit can stay in the class. Keep it in the
minimal coordinate form, so that it reads as pseudocode. When it grows past that, extract a
dedicated coordinator.

### `__init__`

- Write `__init__` as a sequence of `self._init_<thing>(...)` calls and minimal glue. A one-line
  assignment such as `self._root = root` is glue.
- Give each concern its own helper, named `_init_<thing>` after the part that it builds. If the
  part is built only under a condition, name the helper `_maybe_init_<thing>`, and put the
  condition inside the helper.
- A helper reads only the attributes that earlier helpers set. `__init__` holds the order. Pass a
  shared intermediate value as an argument, not through `self`.
- For new construction logic, add a new helper. Do not add an inline block to `__init__`.

### Collaborators

- Give a collaborator the specific values that it needs, by keyword, not the large class itself.
- Let the collaborator return a small frozen dataclass. The large class assigns the result to its
  own attributes. The collaborator does not write attributes of the large class.
- If a collaborator must take the large class, keep that dependency in the smallest leaf, and keep
  it read-only. Say in a comment why the leaf cannot take narrow values.

## Attribute access

Do not use `getattr(obj, "name", default)` or `hasattr(obj, "name")` to read an attribute that is
always there. If someone renames the attribute, the default hides the error. A direct read raises
`AttributeError`. Also, mypy cannot check a defensive read, and `gate/checks/type_hints.py` runs
mypy in strict mode.

Do one of these instead:

1. **Narrow the type with `isinstance`.** Then read the attribute directly.
2. **Always set the attribute**, to `None` if there is no value. Then test `is not None`.
3. **Declare an optional operation in the protocol or the base class.** Give it a default that
   reports no support. Then call it directly. Do not probe for it with `getattr`.

```python
# Bad: the class always sets timeout_s, so the default only hides a rename.
timeout = getattr(config, "timeout_s", 60)
# Good
timeout = config.timeout_s
```

This rule is about a fixed attribute name. A `getattr` with a name computed at run time, such as a
lookup by a name from a config file, is reflection. The rule does not apply to it.

## Dead code

- **Delete code that no entry point reaches.** Do not keep a compatibility shim, an unused option
  or a second implementation of the same thing.
- **Delete what a deletion leaves behind.** When a change removes the last user of a helper, a
  flag, a doc section or a test, remove that item in the same change.
- **Add an API together with its first caller.** Do not add an API for a caller that does not
  exist yet.

## Scope

- Apply these rules to the code that you write or change. Change other code to meet them when you
  edit the same function. Do not make a separate sweep, unless the user asks.
- If a rule conflicts with the code around it, tell the user. Do not mix two styles in one
  function.

## Checklist

- [ ] Each new data container is a frozen dataclass, or has a reason to be mutable.
- [ ] Each function is at 100 lines or fewer. Each file is at 1000 lines or fewer.
- [ ] The main function of each unit reads like pseudocode.
- [ ] No mixin class was added.
- [ ] Each statement in a large class constructs, wires, delegates or coordinates. Its
      `__init__` is a sequence of `_init_*` calls.
- [ ] Each name that only its own module or class uses starts with `_`.
- [ ] Calls with two or more arguments pass them by keyword.
- [ ] Each callee gets the values that it needs, not a whole namespace or store.
- [ ] No `getattr` or `hasattr` guards an attribute that is always there.
- [ ] No code, flag, doc section or test is left without a user.
