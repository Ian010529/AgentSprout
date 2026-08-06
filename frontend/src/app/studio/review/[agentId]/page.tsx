import { TeacherEvaluation } from "@/components/teacher-evaluation";

type TeacherReviewPageProps = {
  params: Promise<{ agentId: string }>;
};

export default async function TeacherReviewPage({ params }: TeacherReviewPageProps) {
  const { agentId } = await params;
  return <TeacherEvaluation agentId={agentId} />;
}
