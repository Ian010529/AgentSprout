import { AgentWorkspace } from "@/components/agent-workspace";

type AgentWorkspacePageProps = {
  params: Promise<{ agentId: string }>;
};

export default async function AgentWorkspacePage({ params }: AgentWorkspacePageProps) {
  const { agentId } = await params;
  return <AgentWorkspace agentId={agentId} />;
}
