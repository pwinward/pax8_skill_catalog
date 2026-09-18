"""The MCP surface. Thin on purpose: it defines tools and delegates.

Tool descriptions are prompt text — they are what a model reads when deciding whether
to call, so they state the result contract rather than just naming the operation.
"""

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .models import FileMap, PublishResult, SkillBundle, SkillRef
from .service import CatalogService

READ_ONLY = ToolAnnotations(read_only_hint=True)
WRITES = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False)


def build_server(service: CatalogService) -> MCPServer:
    server = MCPServer(
        name="skills-catalog",
        instructions=(
            "A shared catalog of reusable AI-assistant skills. Publish a skill once and "
            "any other developer's assistant can discover and retrieve it."
        ),
    )

    @server.tool(
        name="publish_skill",
        description=(
            "Publish a skill to the shared catalog so other developers can reuse it.\n\n"
            "Pass the skill directory as a map of relative path to file contents. The map "
            "must include SKILL.md at the root, carrying 'name' and 'description' in "
            "frontmatter followed by the instruction body. All files must be UTF-8 text.\n\n"
            "Publishing under a name that already exists creates a new version and leaves "
            "earlier versions intact; nothing is ever overwritten.\n\n"
            "On success the result has published=true and the assigned version. If the "
            "bundle is rejected, published=false and no version number is returned — report "
            "the message and the named field to the user rather than retrying unchanged."
        ),
        annotations=WRITES,
    )
    def publish_skill(files: FileMap, publisher: str | None = None) -> PublishResult:
        return service.publish(files, publisher)

    @server.tool(
        name="retrieve_skill",
        description=(
            "Retrieve a published skill from the shared catalog, complete and unchanged.\n\n"
            "Returns a map of relative path to file contents, including SKILL.md — write it "
            "to the skills directory to install the skill. Returns the latest version unless "
            "a version number is given.\n\n"
            "If the skill or version does not exist, found=false and the message says which. "
            "Report that as-is; do not substitute a similarly named skill."
        ),
        annotations=READ_ONLY,
    )
    def retrieve_skill(name: str, version: int | None = None) -> SkillBundle:
        return service.retrieve(name, version)

    @server.tool(
        name="discover_skills",
        description=(
            "Search the shared catalog for skills matching a described need.\n\n"
            "Pass the developer's need as a query in plain words. Returns a list of "
            "matching skills with name, description and latest version — enough to "
            "choose one, which retrieve_skill then fetches in full.\n\n"
            "An empty list means no published skill matches. Say so plainly; do not "
            "offer a skill that is not in the results or suggest one might exist."
        ),
        annotations=READ_ONLY,
    )
    def discover_skills(query: str, limit: int | None = None) -> list[SkillRef]:
        return service.discover(query, limit)

    return server
