import asyncio
import inspect
from annotationlib import Format, get_annotations  # type: ignore[import-not-found]
from contextlib import asynccontextmanager, contextmanager, AsyncExitStack
from dataclasses import dataclass, field
from typing import (
    Annotated,
    Any,
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Callable,
    Generator,
    Iterable,
    Iterator,
    Literal,
    TypeAliasType,
    get_args,
    get_origin,
)

from sevro.request import Request


# --- Parameter source markers ---


@dataclass(frozen=True)
class Path:
    alias: str | None = None


@dataclass(frozen=True)
class Query:
    alias: str | None = None


@dataclass(frozen=True)
class Header:
    alias: str | None = None
    convert_underscores: bool = True


@dataclass(frozen=True)
class Body:
    alias: str | None = None


# --- Core dependency marker ---


@dataclass(frozen=True)
class Depends:
    dependency: Callable[..., Any] | None = None
    use_cache: bool = True
    scope: Literal["function", "request"] | None = None


# --- Parameter specification ---


@dataclass
class ParamSpec:
    name: str
    alias: str
    source: Literal["path", "query", "header", "body"]
    type_annotation: Any
    default: Any  # inspect.Parameter.empty means required


# --- Dependant ---


@dataclass
class Dependant:
    call: Callable[..., Any] | None = None
    name: str | None = None
    path: str | None = None
    use_cache: bool = True
    scope: Literal["function", "request"] | None = None
    path_params: list[ParamSpec] = field(default_factory=list)
    query_params: list[ParamSpec] = field(default_factory=list)
    header_params: list[ParamSpec] = field(default_factory=list)
    body_params: list[ParamSpec] = field(default_factory=list)
    dependencies: list["Dependant"] = field(default_factory=list)
    injected_params: list[tuple[str, type]] = field(default_factory=list)
    request_param_name: str | None = None
    http_connection_param_name: str | None = None

    @property
    def cache_key(self) -> tuple:
        return (self.call,)

    @property
    def is_coroutine_callable(self) -> bool:
        return self.call is not None and inspect.iscoroutinefunction(self.call)

    @property
    def is_async_gen_callable(self) -> bool:
        return self.call is not None and inspect.isasyncgenfunction(self.call)

    @property
    def is_gen_callable(self) -> bool:
        return self.call is not None and inspect.isgeneratorfunction(
            inspect.unwrap(self.call)
        )

    @property
    def computed_scope(self) -> Literal["function", "request"] | None:
        if self.scope is not None:
            return self.scope
        if self.is_gen_callable or self.is_async_gen_callable:
            return "request"
        return None


@dataclass
class ParamDetails:
    type_annotation: Any
    depends: Depends | None
    param_spec: ParamSpec | None


@dataclass
class SolvedDependency:
    values: dict[str, Any]
    errors: list[str]
    dependency_cache: dict[tuple, Any]


# --- Signature utilities ---


def _get_annotations(call: Callable[..., Any]) -> dict[str, Any]:
    """Evaluate all annotations on call, falling back to FORWARDREF on NameError."""
    try:
        return get_annotations(call, format=Format.VALUE)  # type: ignore[call-arg]
    except NameError:
        return get_annotations(call, format=Format.FORWARDREF)  # type: ignore[call-arg]


def get_typed_signature(call: Callable[..., Any]) -> inspect.Signature:
    annotations = _get_annotations(inspect.unwrap(call))
    signature = inspect.signature(call)
    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=annotations.get(param.name, inspect.Parameter.empty),
        )
        for param in signature.parameters.values()
    ]
    return inspect.Signature(typed_params)


def get_typed_return_annotation(call: Callable[..., Any]) -> Any:
    return _get_annotations(inspect.unwrap(call)).get("return")


# --- Path param extraction ---


def get_path_param_names(path: str) -> set[str]:
    """Extract parameter names from a route pattern like /user/:id."""
    import re

    return set(re.findall(r"[\*:](\w+)", path))


# --- Stream type detection ---

_STREAM_ORIGINS = {
    AsyncIterable,
    AsyncIterator,
    AsyncGenerator,
    Iterable,
    Iterator,
    Generator,
}


def get_stream_item_type(annotation: Any) -> Any | None:
    origin = get_origin(annotation)
    if origin is not None and origin in _STREAM_ORIGINS:
        type_args = get_args(annotation)
        return type_args[0] if type_args else Any
    return None


# --- Parameter analysis ---


def analyze_param(
    *,
    param_name: str,
    annotation: Any,
    value: Any,
    is_path_param: bool,
) -> ParamDetails:
    depends: Depends | None = None
    type_annotation: Any = Any
    marker: Path | Query | Header | Body | None = None

    if isinstance(annotation, TypeAliasType):
        annotation = annotation.__value__

    if annotation is not inspect.Parameter.empty:
        type_annotation = annotation

    # Unwrap Annotated[T, marker, ...]
    if get_origin(type_annotation) is Annotated:
        annotated_args = get_args(type_annotation)
        type_annotation = annotated_args[0]
        for arg in annotated_args[1:]:
            if isinstance(arg, Depends) and depends is None:
                depends = arg
            elif isinstance(arg, (Path, Query, Header, Body)) and marker is None:
                marker = arg

    # Depends from default value
    if isinstance(value, Depends):
        assert depends is None, (
            f"Cannot specify Depends in Annotated and as a default value for {param_name!r}"
        )
        depends = value

    # Depends with no dependency uses the type annotation as the dependency
    if depends is not None and depends.dependency is None:
        depends = Depends(
            dependency=type_annotation,
            use_cache=depends.use_cache,
            scope=depends.scope,
        )

    if depends is not None:
        return ParamDetails(
            type_annotation=type_annotation, depends=depends, param_spec=None
        )

    # Special injection types
    if _is_request_type(type_annotation):
        return ParamDetails(
            type_annotation=type_annotation, depends=None, param_spec=None
        )

    # Determine param source and build ParamSpec
    default = value if value is not inspect.Parameter.empty else inspect.Parameter.empty

    if isinstance(marker, Path) or (marker is None and is_path_param):
        alias = (marker.alias if isinstance(marker, Path) else None) or param_name
        param_spec = ParamSpec(
            name=param_name,
            alias=alias,
            source="path",
            type_annotation=type_annotation,
            default=default,
        )
    elif isinstance(marker, Header):
        raw_alias = marker.alias or param_name
        if marker.convert_underscores:
            raw_alias = raw_alias.replace("_", "-")
        param_spec = ParamSpec(
            name=param_name,
            alias=raw_alias.lower(),
            source="header",
            type_annotation=type_annotation,
            default=default,
        )
    elif isinstance(marker, Body):
        alias = marker.alias or param_name
        param_spec = ParamSpec(
            name=param_name,
            alias=alias,
            source="body",
            type_annotation=type_annotation,
            default=default,
        )
    else:
        # Default: query (covers marker=None non-path, and explicit Query marker)
        alias = (marker.alias if isinstance(marker, Query) else None) or param_name
        param_spec = ParamSpec(
            name=param_name,
            alias=alias,
            source="query",
            type_annotation=type_annotation,
            default=default,
        )

    return ParamDetails(
        type_annotation=type_annotation, depends=None, param_spec=param_spec
    )


def _is_request_type(annotation: Any) -> bool:
    return annotation is Request or (
        isinstance(annotation, type) and issubclass(annotation, Request)
    )


def _is_http_connection_type(annotation: Any) -> bool:
    return annotation is Request or (
        isinstance(annotation, type) and issubclass(annotation, Request)
    )


_PRIMITIVE_TYPES = {str, int, float, bool, bytes, type(None)}


def _is_injectable_type(annotation: Any) -> bool:
    return (
        isinstance(annotation, type)
        and annotation not in _PRIMITIVE_TYPES
        and annotation is not Any
        and not _is_request_type(annotation)
    )


# --- Dependant building ---


def get_dependant(
    *,
    path: str,
    call: Callable[..., Any],
    name: str | None = None,
    use_cache: bool = True,
    scope: Literal["function", "request"] | None = None,
) -> Dependant:
    dependant = Dependant(
        call=call, name=name, path=path, use_cache=use_cache, scope=scope
    )
    path_param_names = get_path_param_names(path)
    endpoint_signature = get_typed_signature(call)

    for param_name, param in endpoint_signature.parameters.items():
        is_path_param = param_name in path_param_names
        if not is_path_param and _is_injectable_type(param.annotation):
            dependant.injected_params.append((param_name, param.annotation))
            continue
        param_details = analyze_param(
            param_name=param_name,
            annotation=param.annotation,
            value=param.default,
            is_path_param=is_path_param,
        )

        if param_details.depends is not None:
            assert param_details.depends.dependency
            sub_dependant = get_dependant(
                path=path,
                call=param_details.depends.dependency,
                name=param_name,
                use_cache=param_details.depends.use_cache,
                scope=param_details.depends.scope,
            )
            dependant.dependencies.append(sub_dependant)
            continue

        if param_details.param_spec is None:
            # Special injection (Request)
            ann = param_details.type_annotation
            if _is_request_type(ann):
                dependant.request_param_name = param_name
            continue

        spec = param_details.param_spec
        if spec.source == "path":
            dependant.path_params.append(spec)
        elif spec.source == "query":
            dependant.query_params.append(spec)
        elif spec.source == "header":
            dependant.header_params.append(spec)
        else:
            dependant.body_params.append(spec)

    return dependant


def get_parameterless_sub_dependant(*, depends: Depends, path: str) -> Dependant:
    assert callable(depends.dependency), (
        "A parameter-less dependency must have a callable dependency"
    )
    return get_dependant(path=path, call=depends.dependency, scope=depends.scope)


def get_flat_dependant(
    dependant: Dependant,
    *,
    skip_repeats: bool = False,
    visited: list[tuple] | None = None,
) -> Dependant:
    if visited is None:
        visited = []
    visited.append(dependant.cache_key)

    flat = Dependant(
        call=dependant.call,
        name=dependant.name,
        path=dependant.path,
        use_cache=dependant.use_cache,
        scope=dependant.scope,
        path_params=dependant.path_params.copy(),
        query_params=dependant.query_params.copy(),
        header_params=dependant.header_params.copy(),
        body_params=dependant.body_params.copy(),
        request_param_name=dependant.request_param_name,
        http_connection_param_name=dependant.http_connection_param_name,
    )

    for sub in dependant.dependencies:
        if skip_repeats and sub.cache_key in visited:
            continue
        flat_sub = get_flat_dependant(sub, skip_repeats=skip_repeats, visited=visited)
        flat.path_params.extend(flat_sub.path_params)
        flat.query_params.extend(flat_sub.query_params)
        flat.header_params.extend(flat_sub.header_params)
        flat.body_params.extend(flat_sub.body_params)
        flat.dependencies.append(flat_sub)

    return flat


# --- Value conversion ---


def _unwrap_optional(annotation: Any) -> Any:
    """Return the inner type of X | None, or the annotation unchanged."""
    args = get_args(annotation)
    if not args:
        return annotation
    non_none = [a for a in args if a is not type(None)]
    if len(non_none) == len(args):
        return annotation  # no None in the union
    return non_none[0] if len(non_none) == 1 else annotation


def _convert(
    value: str | None,
    type_annotation: Any,
    param_name: str,
    default: Any,
) -> tuple[Any, str | None]:
    """Convert a string value to the target type. Returns (converted, error_message)."""
    if value is None or value == "":
        if default is inspect.Parameter.empty:
            return None, f"missing required parameter '{param_name}'"
        return default, None
    inner = _unwrap_optional(type_annotation)
    if inner is Any or inner is inspect.Parameter.empty or inner is str:
        return value, None
    try:
        return inner(value), None
    except (ValueError, TypeError) as e:
        return None, f"invalid value for '{param_name}': {e}"


# --- Generator helpers ---


@asynccontextmanager
async def _contextmanager_in_threadpool(cm):
    value = await asyncio.to_thread(cm.__enter__)
    try:
        yield value
    except Exception as exc:
        if not await asyncio.to_thread(cm.__exit__, type(exc), exc, exc.__traceback__):
            raise
    else:
        await asyncio.to_thread(cm.__exit__, None, None, None)


async def _solve_generator(
    *, dependant: Dependant, stack: AsyncExitStack, sub_values: dict[str, Any]
) -> Any:
    assert dependant.call
    if dependant.is_async_gen_callable:
        cm = asynccontextmanager(dependant.call)(**sub_values)
    else:
        cm = _contextmanager_in_threadpool(contextmanager(dependant.call)(**sub_values))
    return await stack.enter_async_context(cm)


# --- Dependency solving ---


async def solve_dependencies(
    *,
    request: Request,
    dependant: Dependant,
    path_params: dict[str, str],
    body: dict[str, Any] | None = None,
    dependency_cache: dict[tuple, Any] | None = None,
    dependency_overrides: dict[Callable, Callable] | None = None,
    async_exit_stack: AsyncExitStack,
    registry: dict[type, Any] | None = None,
) -> SolvedDependency:
    if dependency_cache is None:
        dependency_cache = {}
    values: dict[str, Any] = {}
    errors: list[str] = []

    for sub_dependant in dependant.dependencies:
        assert sub_dependant.call
        call = sub_dependant.call
        use_sub_dependant = sub_dependant

        if dependency_overrides and call in dependency_overrides:
            call = dependency_overrides[call]
            use_sub_dependant = get_dependant(
                path=sub_dependant.path or "",
                call=call,
                name=sub_dependant.name,
                use_cache=sub_dependant.use_cache,
                scope=sub_dependant.scope,
            )

        solved_result = await solve_dependencies(
            request=request,
            dependant=use_sub_dependant,
            path_params=path_params,
            body=body,
            dependency_cache=dependency_cache,
            dependency_overrides=dependency_overrides,
            async_exit_stack=async_exit_stack,
        )

        if solved_result.errors:
            errors.extend(solved_result.errors)
            continue

        cache_key = use_sub_dependant.cache_key
        if sub_dependant.use_cache and cache_key in dependency_cache:
            solved = dependency_cache[cache_key]
        elif (
            use_sub_dependant.is_gen_callable or use_sub_dependant.is_async_gen_callable
        ):
            solved = await _solve_generator(
                dependant=use_sub_dependant,
                stack=async_exit_stack,
                sub_values=solved_result.values,
            )
        elif use_sub_dependant.is_coroutine_callable:
            solved = await call(**solved_result.values)
        else:
            solved = await asyncio.to_thread(call, **solved_result.values)

        if sub_dependant.name is not None:
            values[sub_dependant.name] = solved
        if cache_key not in dependency_cache:
            dependency_cache[cache_key] = solved

    # Path params
    for spec in dependant.path_params:
        raw = path_params.get(spec.alias)
        val, err = _convert(raw, spec.type_annotation, spec.name, spec.default)
        if err:
            errors.append(err)
        else:
            values[spec.name] = val

    # Query params
    if dependant.query_params:
        query_dict = request.params
        for spec in dependant.query_params:
            raw_list = query_dict.get(spec.alias)
            raw = raw_list[0] if raw_list else None
            val, err = _convert(raw, spec.type_annotation, spec.name, spec.default)
            if err:
                errors.append(err)
            else:
                values[spec.name] = val

    # Header params
    for spec in dependant.header_params:
        raw = request.scope.headers.get(spec.alias)
        val, err = _convert(raw, spec.type_annotation, spec.name, spec.default)
        if err:
            errors.append(err)
        else:
            values[spec.name] = val

    # Body params
    if dependant.body_params:
        if body is None:
            try:
                body = await request.json()
            except Exception:
                body = {}
        for spec in dependant.body_params:
            raw = body.get(spec.alias) if isinstance(body, dict) else None
            if raw is None:
                if spec.default is inspect.Parameter.empty:
                    errors.append(f"missing required body parameter '{spec.name}'")
                else:
                    values[spec.name] = spec.default
            else:
                ann = spec.type_annotation
                if ann is Any or ann is inspect.Parameter.empty:
                    values[spec.name] = raw
                elif isinstance(ann, type) and isinstance(raw, ann):
                    values[spec.name] = raw
                else:
                    try:
                        values[spec.name] = ann(raw) if isinstance(ann, type) else raw
                    except (ValueError, TypeError) as e:
                        errors.append(f"invalid body parameter '{spec.name}': {e}")

    # Special injections
    if dependant.request_param_name:
        values[dependant.request_param_name] = request
    if dependant.http_connection_param_name:
        values[dependant.http_connection_param_name] = request

    # Registry injections
    if registry and dependant.injected_params:
        for param_name, t in dependant.injected_params:
            if t in registry:
                values[param_name] = registry[t]

    return SolvedDependency(
        values=values, errors=errors, dependency_cache=dependency_cache
    )
