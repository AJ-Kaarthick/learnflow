/**
 * Converts generated learning artifacts into clean Markdown for export.
 * Kept alongside treeToMarkdown (the mind map's own tree-to-Markdown
 * converter) so every panel's "Download" button formats its content
 * the same way: an H1 title followed by the artifact's content.
 */

export function summaryToMarkdown(summary) {
  return `# Summary\n\n${summary.content}`;
}

export function flashcardsToMarkdown(flashcards) {
  const cards = flashcards
    .map((card) => `**Q:** ${card.question}\n\n**A:** ${card.answer}`)
    .join("\n\n---\n\n");
  return `# Flashcards\n\n${cards}`;
}

export function quizToMarkdown(questions) {
  const items = questions
    .map((question, index) => {
      const optionLines = question.options
        .map((option, optionIndex) => `- ${String.fromCharCode(65 + optionIndex)}. ${option}`)
        .join("\n");
      const correctLetter = String.fromCharCode(65 + question.correct_answer_index);
      return `${index + 1}. ${question.question}\n\n${optionLines}\n\n**Correct answer:** ${correctLetter}`;
    })
    .join("\n\n");
  return `# Quiz\n\n${items}`;
}
