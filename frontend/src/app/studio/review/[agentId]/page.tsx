import { TeacherEvaluation } from "@/components/teacher-evaluation";

export default async function TeacherReviewPage({ params }: PageProps<"/studio/review/[agentId]">) {
  const { agentId } = await params;
  return <TeacherEvaluation agentId={agentId} />;
}
