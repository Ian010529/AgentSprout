import { PublishedAgent } from "@/components/published-agent";

export default async function PublishedAgentPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <PublishedAgent slug={slug} />;
}
