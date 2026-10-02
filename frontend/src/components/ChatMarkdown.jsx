import ReactMarkdown from 'react-markdown'

// Styles for each Markdown element in an Ask FlockGuard reply. Bold is the
// AI's way of marking "this is the thing to do", so it gets the strongest
// ink. react-markdown never renders raw HTML from the model.
const COMPONENTS = {
  p: (props) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
  strong: (props) => <strong className="font-bold text-navy" {...props} />,
  ul: (props) => <ul className="my-2 list-disc space-y-1 pl-5 marker:text-ai" {...props} />,
  ol: (props) => <ol className="my-2 list-decimal space-y-1.5 pl-5 marker:font-semibold marker:text-ai" {...props} />,
  li: (props) => <li className="pl-1" {...props} />,
  h1: (props) => <h3 className="mt-3 mb-1 text-sm font-bold text-navy first:mt-0" {...props} />,
  h2: (props) => <h3 className="mt-3 mb-1 text-sm font-bold text-navy first:mt-0" {...props} />,
  h3: (props) => <h3 className="mt-3 mb-1 text-sm font-bold text-navy first:mt-0" {...props} />,
  h4: (props) => <h4 className="mt-2 mb-1 text-sm font-semibold text-navy first:mt-0" {...props} />,
  a: (props) => <a className="font-semibold text-ai underline" target="_blank" rel="noreferrer" {...props} />,
  em: (props) => <em className="text-secondary" {...props} />,
  hr: () => <hr className="my-3 border-hairline" />,
}

export default function ChatMarkdown({ text }) {
  return <ReactMarkdown components={COMPONENTS}>{text}</ReactMarkdown>
}
