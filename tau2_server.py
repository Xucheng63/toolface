"""
tau2_server.py — TAU2 工具本地 HTTP 服务器

把 airline / retail / telecom 三个域的工具全部暴露为 HTTP API，
供 index.html 的 "Try It" 功能调用。

用法：
  pip install fastapi uvicorn
  python tau2_server.py

  # 或指定端口
  python tau2_server.py --port 8000

端点：
  GET  /                              → 服务器状态 + 所有可用工具列表
  GET  /tools                         → 所有工具的 schema
  POST /tools/airline/{tool_name}     → 执行 airline agent 工具
  POST /tools/retail/{tool_name}      → 执行 retail agent 工具
  POST /tools/telecom/{tool_name}     → 执行 telecom agent 工具
  POST /tools/telecom_user/{tool_name}→ 执行 telecom user 工具

文件布局（所有 standalone 目录需要与本文件同级或在 toolface/ 下）：
  toolface/
  ├── tau2_server.py           ← 本文件
  ├── index.html
  ├── airline_standalone/
  │   ├── data_model.py
  │   ├── tools.py
  │   ├── db.json
  │   └── ... (其他 standalone 文件)
  ├── retail_standalone/
  │   ├── data_model.py
  │   ├── tools.py
  │   ├── db.json
  │   └── ...
  └── telecom_standalone/
      ├── data_model.py
      ├── tools.py
      ├── user_tools.py
      ├── db.toml
      ├── user_db.toml
      └── ...
"""

import argparse
import json
import sys
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Path setup ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

AIRLINE_DIR  = BASE_DIR / "airline_standalone"
RETAIL_DIR   = BASE_DIR / "retail_standalone"
TELECOM_DIR  = BASE_DIR / "telecom_standalone"


def add_path(p: Path):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


# ── Load tools (lazy, with error handling) ────────────────────────

_cache = {}
_load_errors = {}


def load_airline():
    if "airline" in _cache:
        return _cache["airline"]
    try:
        add_path(AIRLINE_DIR)
        import importlib.util

        def _load_mod(reg_name, path):
            spec = importlib.util.spec_from_file_location(reg_name, str(path))
            mod  = importlib.util.module_from_spec(spec)
            sys.modules[reg_name] = mod
            spec.loader.exec_module(mod)
            return mod

        # Load airline infra with unique prefixed names
        _load_mod("al_tau2_utils",  AIRLINE_DIR / "tau2_utils.py")
        _load_mod("al_db",          AIRLINE_DIR / "db.py")
        _load_mod("al_tool",        AIRLINE_DIR / "tool.py")
        _load_mod("al_toolkit",     AIRLINE_DIR / "toolkit.py")
        _load_mod("al_utils",       AIRLINE_DIR / "airline_utils.py")

        # Bind generic names so data_model/tools internal imports resolve
        sys.modules["tau2_utils"]   = sys.modules["al_tau2_utils"]
        sys.modules["db"]           = sys.modules["al_db"]
        sys.modules["tool"]         = sys.modules["al_tool"]
        sys.modules["toolkit"]      = sys.modules["al_toolkit"]
        sys.modules["airline_utils"] = sys.modules["al_utils"]

        al_dm = _load_mod("al_data_model", AIRLINE_DIR / "data_model.py")
        sys.modules["data_model"] = al_dm

        al_t  = _load_mod("al_tools", AIRLINE_DIR / "tools.py")

        # Clean up generic names so retail/telecom load their own versions
        for _m in ["data_model", "toolkit", "tool", "db",
                   "tau2_utils", "airline_utils"]:
            sys.modules.pop(_m, None)

        db = al_dm.FlightDB.load(str(AIRLINE_DIR / "db.json"))
        _cache["airline"] = al_t.AirlineTools(db)
        print(f"✅ Airline tools loaded ({len(_cache['airline'].get_tools())} tools)")
        return _cache["airline"]
    except Exception as e:
        import traceback; traceback.print_exc()
        _load_errors["airline"] = str(e)
        print(f"❌ Airline load error: {e}")
        return None



def load_retail():
    if "retail" in _cache:
        return _cache["retail"]
    try:
        # Add retail_standalone to sys.path so internal imports resolve
        add_path(RETAIL_DIR)
        import importlib.util

        def load_module(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            return mod

        load_module("retail_tau2_utils",  RETAIL_DIR / "tau2_utils.py")
        load_module("retail_db_base",      RETAIL_DIR / "db.py")
        load_module("retail_tool_base",    RETAIL_DIR / "tool.py")
        load_module("retail_toolkit_base", RETAIL_DIR / "toolkit.py")
        load_module("retail_utils_mod",    RETAIL_DIR / "retail_utils.py")
        retail_dm = load_module("retail_data_model", RETAIL_DIR / "data_model.py")
        # Temporarily remap shared names so retail_tools internal imports resolve correctly
        _saved = {k: sys.modules.get(k) for k in ["data_model", "toolkit", "tool", "db", "tau2_utils", "retail_utils"]}
        sys.modules["data_model"]  = retail_dm
        sys.modules["toolkit"]     = sys.modules.get("retail_toolkit_base")
        sys.modules["tool"]        = sys.modules.get("retail_tool_base")
        sys.modules["db"]          = sys.modules.get("retail_db_base")
        sys.modules["tau2_utils"]  = sys.modules.get("retail_tau2_utils")
        sys.modules["retail_utils"] = sys.modules.get("retail_utils_mod")
        retail_t  = load_module("retail_tools", RETAIL_DIR / "tools.py")
        for k, v in _saved.items():  # restore
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v

        db = retail_dm.RetailDB.load(str(RETAIL_DIR / "db.json"))
        _cache["retail"] = retail_t.RetailTools(db)
        print(f"✅ Retail tools loaded ({len(_cache['retail'].get_tools())} tools)")
        return _cache["retail"]
    except Exception as e:
        _load_errors["retail"] = str(e)
        print(f"❌ Retail load error: {e}")
        return None


def load_telecom():
    if "tc_agent" in _cache:
        return _cache["tc_agent"], _cache["tc_user"]
    try:
        add_path(TELECOM_DIR)
        import importlib.util, types

        # ── Build a TOML-aware tau2_utils module ──────────────────
        def _toml_load_file(path):
            import json as _j
            p = str(path)
            if p.endswith('.toml'):
                try:
                    import tomllib as _t
                except ImportError:
                    import tomli as _t
                with open(p, 'rb') as f:
                    return _t.load(f)
            with open(p, 'r', encoding='utf-8') as f:
                return _j.load(f)

        def _load_mod(reg_name, path, extra_globals=None):
            """Load a module from path, register as reg_name in sys.modules."""
            spec = importlib.util.spec_from_file_location(reg_name, str(path))
            mod  = importlib.util.module_from_spec(spec)
            if extra_globals:
                mod.__dict__.update(extra_globals)
            sys.modules[reg_name] = mod
            spec.loader.exec_module(mod)
            return mod

        # tau2_utils with TOML support
        tau2 = _load_mod("tc_tau2_utils", TELECOM_DIR / "tau2_utils.py")
        tau2.load_file = _toml_load_file   # patch after load

        # Re-register as "tau2_utils" so db.py's "from tau2_utils import load_file" works
        sys.modules["tau2_utils"] = tau2

        # Load shared infra
        db_mod      = _load_mod("tc_db",      TELECOM_DIR / "db.py")
        tool_mod    = _load_mod("tc_tool",    TELECOM_DIR / "tool.py")
        toolkit_mod = _load_mod("tc_toolkit", TELECOM_DIR / "toolkit.py")
        utils_mod   = _load_mod("tc_telecom_utils", TELECOM_DIR / "telecom_utils.py")

        # Bind generic names that data_model/tools import from
        sys.modules["db"]            = db_mod
        sys.modules["tool"]          = tool_mod
        sys.modules["toolkit"]       = toolkit_mod
        sys.modules["telecom_utils"] = utils_mod

        # Load domain models and tools
        dm  = _load_mod("tc_data_model",      TELECOM_DIR / "data_model.py")
        udm = _load_mod("tc_user_data_model", TELECOM_DIR / "user_data_model.py")
        sys.modules["data_model"]     = dm
        sys.modules["user_data_model"] = udm

        t_tools  = _load_mod("tc_tools",      TELECOM_DIR / "tools.py")
        ut_tools = _load_mod("tc_user_tools", TELECOM_DIR / "user_tools.py")

        # Clean up generic names
        for _m in ["data_model","user_data_model","toolkit","tool",
                   "db","tau2_utils","telecom_utils"]:
            sys.modules.pop(_m, None)

        # Instantiate
        db      = dm.TelecomDB.load(str(TELECOM_DIR / "db.toml"))
        user_db = udm.TelecomUserDB.load(str(TELECOM_DIR / "user_db.toml"))
        _cache["tc_agent"] = t_tools.TelecomTools(db)
        _cache["tc_user"]  = ut_tools.TelecomUserTools(user_db)
        n_agent = len(_cache["tc_agent"].get_tools())
        n_user  = len(_cache["tc_user"].get_tools())
        print(f"✅ Telecom tools loaded (agent: {n_agent}, user: {n_user})")
        return _cache["tc_agent"], _cache["tc_user"]
    except Exception as e:
        import traceback; traceback.print_exc()
        _load_errors["telecom"] = str(e)
        print(f"❌ Telecom load error: {e}")
        return None, None


def serialize(obj: Any) -> Any:
    """Convert pydantic models, dates, enums etc. to JSON-safe types."""
    try:
        from pydantic import BaseModel as PydanticBase
        if isinstance(obj, PydanticBase):
            return obj.model_dump()
    except Exception:
        pass
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, list):
        return [serialize(i) for i in obj]
    if isinstance(obj, tuple):
        return [serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if hasattr(obj, 'value'):  # Enum
        return obj.value
    return obj


# ── FastAPI app ───────────────────────────────────────────────────

app = FastAPI(
    title="TAU2 Tool Server",
    description="Local HTTP server exposing TAU2 airline/retail/telecom tools for real execution",
    version="1.0.0",
)

# Allow index.html (file://) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ToolRequest(BaseModel):
    arguments: Dict[str, Any] = {}


# ── Root / Status ─────────────────────────────────────────────────

@app.get("/")
def root():
    airline = load_airline()
    agent, user = load_telecom()
    retail = load_retail()

    return {
        "status": "ok",
        "domains": {
            "airline": {
                "loaded": airline is not None,
                "tools": list(airline.get_tools().keys()) if airline else [],
                "error": _load_errors.get("airline"),
            },
            "retail": {
                "loaded": retail is not None,
                "tools": list(retail.get_tools().keys()) if retail else [],
                "error": _load_errors.get("retail"),
            },
            "telecom": {
                "loaded": agent is not None,
                "agent_tools": list(agent.get_tools().keys()) if agent else [],
                "user_tools": list(user.get_tools().keys()) if user else [],
                "error": _load_errors.get("telecom"),
            },
        }
    }


# ── Airline ───────────────────────────────────────────────────────

@app.post("/tools/airline/{tool_name}")
def run_airline_tool(tool_name: str, body: ToolRequest):
    tools = load_airline()
    if tools is None:
        raise HTTPException(503, f"Airline tools not loaded: {_load_errors.get('airline', 'unknown error')}")
    if not tools.has_tool(tool_name):
        available = list(tools.get_tools().keys())
        raise HTTPException(404, f"Tool '{tool_name}' not found. Available: {available}")
    try:
        result = tools.use_tool(tool_name, **body.arguments)
        return {"ok": True, "tool": tool_name, "result": serialize(result)}
    except Exception as e:
        raise HTTPException(400, f"Tool execution error: {e}")


# ── Retail ────────────────────────────────────────────────────────

@app.post("/tools/retail/{tool_name}")
def run_retail_tool(tool_name: str, body: ToolRequest):
    tools = load_retail()
    if tools is None:
        raise HTTPException(503, f"Retail tools not loaded: {_load_errors.get('retail', 'unknown error')}")
    if not tools.has_tool(tool_name):
        available = list(tools.get_tools().keys())
        raise HTTPException(404, f"Tool '{tool_name}' not found. Available: {available}")
    try:
        result = tools.use_tool(tool_name, **body.arguments)
        return {"ok": True, "tool": tool_name, "result": serialize(result)}
    except Exception as e:
        raise HTTPException(400, f"Tool execution error: {e}")


# ── Telecom Agent ─────────────────────────────────────────────────

@app.post("/tools/telecom/{tool_name}")
def run_telecom_agent_tool(tool_name: str, body: ToolRequest):
    agent, _ = load_telecom()
    if agent is None:
        raise HTTPException(503, f"Telecom tools not loaded: {_load_errors.get('telecom', 'unknown error')}")
    if not agent.has_tool(tool_name):
        available = list(agent.get_tools().keys())
        raise HTTPException(404, f"Tool '{tool_name}' not found. Available: {available}")
    try:
        result = agent.use_tool(tool_name, **body.arguments)
        return {"ok": True, "tool": tool_name, "result": serialize(result)}
    except Exception as e:
        raise HTTPException(400, f"Tool execution error: {e}")


# ── Telecom User ──────────────────────────────────────────────────

@app.post("/tools/telecom_user/{tool_name}")
def run_telecom_user_tool(tool_name: str, body: ToolRequest):
    _, user = load_telecom()
    if user is None:
        raise HTTPException(503, f"Telecom user tools not loaded: {_load_errors.get('telecom', 'unknown error')}")
    if not user.has_tool(tool_name):
        available = list(user.get_tools().keys())
        raise HTTPException(404, f"Tool '{tool_name}' not found. Available: {available}")
    try:
        result = user.use_tool(tool_name, **body.arguments)
        return {"ok": True, "tool": tool_name, "result": serialize(result)}
    except Exception as e:
        raise HTTPException(400, f"Tool execution error: {e}")


# ── Schema listing ────────────────────────────────────────────────

@app.get("/tools")
def list_tools():
    """List all available tools with their schemas."""
    out = {}
    airline = load_airline()
    if airline:
        out["airline"] = {
            name: tool.openai_schema
            for name, tool in airline.get_tools().items()
        }
    retail = load_retail()
    if retail:
        out["retail"] = {
            name: tool.openai_schema
            for name, tool in retail.get_tools().items()
        }
    agent, user = load_telecom()
    if agent:
        out["telecom"] = {
            name: tool.openai_schema
            for name, tool in agent.get_tools().items()
        }
    if user:
        out["telecom_user"] = {
            name: tool.openai_schema
            for name, tool in user.get_tools().items()
        }
    return out


# ── Entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="TAU2 Tool Server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f"TAU2 Tool Server")
    print(f"  http://{args.host}:{args.port}")
    print(f"  Airline:  {AIRLINE_DIR}")
    print(f"  Retail:   {RETAIL_DIR}")
    print(f"  Telecom:  {TELECOM_DIR}")
    print(f"{'='*55}\n")

    # Pre-load all tools
    load_airline()
    load_retail()
    load_telecom()

    uvicorn.run(
        "tau2_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
