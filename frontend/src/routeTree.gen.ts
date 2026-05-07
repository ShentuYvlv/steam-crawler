import { rootRoute } from "@/routes/__root";
import { gamesRoute } from "@/routes/games";
import { indexRoute } from "@/routes/index";
import { replyRecordsRoute } from "@/routes/reply-records";
import { replyStrategiesRoute } from "@/routes/reply-strategies";
import { reviewsRoute } from "@/routes/reviews";
import { taskQueueRoute } from "@/routes/task-queue";
import { tasksRoute } from "@/routes/tasks";
import { usersRoute } from "@/routes/users";

export const routeTree = rootRoute.addChildren([
  indexRoute,
  gamesRoute,
  reviewsRoute,
  replyStrategiesRoute,
  tasksRoute,
  taskQueueRoute,
  replyRecordsRoute,
  usersRoute
]);
