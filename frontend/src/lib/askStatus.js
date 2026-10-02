// What Ask FlockGuard says while it works on a question - matched to the
// topic so a Christmas-sales question doesn't say "Checking your farm
// records". Purely cosmetic, instant and free (no AI call); roughly mirrors
// the backend's skill routing (app/agent/agent_router.py). The first match
// wins, so the more specific topics come first. Each topic is a short
// sequence the chat steps through while it waits; the last step stays.
const TOPICS = [
  {
    words: ['christmas', 'xmas', 'festive', 'holiday', 'easter', 'sallah', 'eid', 'ramadan', 'new year', 'season'],
    stages: [
      'Planning for the festive season...',
      'Looking at your flock size and bird age...',
      'Putting together ways to protect your birds and earn more...',
    ],
  },
  {
    words: ['revenue', 'profit', 'money', 'earn', 'income', 'sell', 'price', 'market', 'customer', 'buyer', 'cost', 'business'],
    stages: [
      'Looking at ways to earn more from your birds...',
      'Checking your flock numbers...',
      'Preparing practical selling tips...',
    ],
  },
  {
    words: ['which house', 'check first', 'inspect first', 'priority', 'attention first', 'highest risk'],
    stages: ['Comparing risk across your houses...', 'Ranking houses by what needs you first...', 'Writing your answer...'],
  },
  {
    words: ['look at', 'look for', 'checklist', 'what should i check'],
    stages: ['Preparing what to look for in your birds...', "Checking your flock's recent signs...", 'Writing your checklist...'],
  },
  {
    words: ['heat', 'hot', 'cold', 'temperature', 'ventilation', 'fresh air', 'smell', 'ammonia', 'litter', 'wet', 'rain'],
    stages: ['Looking at your house conditions...', 'Checking how your birds have been doing...', 'Preparing practical fixes...'],
  },
  {
    words: ['warnings', 'alerts', 'sorted out', 'unresolved', 'open warning'],
    stages: ['Checking your open warnings...', 'Seeing which ones still need you...', 'Writing your answer...'],
  },
  {
    words: ['summarize', 'summarise', 'summary', 'brief', 'overview', 'today', 'how is my farm'],
    stages: ["Gathering today's checks and warnings...", 'Summing up your farm...', 'Writing your update...'],
  },
  {
    words: ['sick', 'cough', 'sneez', 'diarr', 'dropping', 'dying', 'died', 'dead', 'disease', 'vaccin', 'vet', 'weak', 'swollen', 'limp', 'mortality'],
    stages: [
      'Reviewing the signs you described...',
      "Comparing with your flock's recent checks...",
      'Preparing safe next steps...',
    ],
  },
  {
    words: ['why', 'flagged', 'warning', 'critical', 'wrong', 'changed', 'problem'],
    stages: ['Looking into what changed...', 'Checking recent checks and warnings...', 'Working out the likely cause...'],
  },
  {
    words: ['feed', 'water', 'drink', 'eating', 'weight', 'grow'],
    stages: ['Looking at feed and water patterns...', 'Comparing with your recent checks...', 'Preparing advice...'],
  },
  {
    words: ['house', 'flock', 'my birds', 'my farm', 'alert', 'week', 'yesterday', 'trend', 'compare'],
    stages: ['Checking your farm records...', 'Looking at recent trends...', 'Writing your answer...'],
  },
]

const GENERAL = {
  stages: ['Looking through trusted poultry guides...', 'Preparing a clear answer...', 'Writing your answer...'],
}

// Keywords match at the start of a word ("vet" -> "veterinary", but "hot"
// never matches inside "photo").
const startsWord = (text, word) => new RegExp(`\\b${word}`).test(text)

export function statusStagesFor(question) {
  const q = (question || '').toLowerCase()
  return (TOPICS.find((topic) => topic.words.some((w) => startsWord(q, w))) || GENERAL).stages
}
