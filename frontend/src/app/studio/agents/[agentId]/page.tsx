import { AgentWorkspace } from "@/components/agent-workspace";

export default async function AgentWorkspacePage({ params }: PageProps<"/studio/agents/[agentId]">) {
  const { agentId } = await params;
  return <AgentWorkspace agentId={agentId} />;
}
