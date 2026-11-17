from mcp.server.fastmcp import FastMCP

from .tools import Engine


def build_server(engine=None):
    engine = engine or Engine()
    mcp = FastMCP("leanline")

    @mcp.tool()
    def read_relevant(path_or_folder: str, question: str, max_tokens: int = 2000, section: str = "") -> str:
        """Return only the sections of a file or folder that best answer a question, instead of the whole files.
        Supports .md .txt .docx .pdf .pptx .log. Each result names its file and section; a list of other
        matching sections is appended so you can ask for more with section="<name>".
        Use this instead of opening documents whole. Leave section empty to search by question."""
        return engine.read_relevant(path_or_folder, question, max_tokens, section)

    @mcp.tool()
    def compact(file_or_text: str, kind: str = "auto", full: bool = False) -> str:
        """Shrink a large log, JSON, HTML page or text (a file path or the text itself).
        kind: auto, log, json, html or text. Logs keep errors in context and collapse repeats; JSON keeps
        structure plus samples; HTML keeps main text. The result always states what was dropped.
        Pass full=true to get the original unchanged."""
        return engine.compact(file_or_text, kind, full)

    @mcp.tool()
    def remember(path: str, digest: str) -> str:
        """Store a short digest of a file you have read, keyed by the file's content hash,
        so you can skip re-reading it while it is unchanged."""
        return engine.remember(path, digest)

    @mcp.tool()
    def recall(path: str) -> str:
        """Return the stored digest for a file if the file is unchanged since remember was called;
        otherwise say it is stale or missing."""
        return engine.recall(path)

    return mcp


def main(home=None):
    build_server(Engine(home)).run()  # stdio transport
